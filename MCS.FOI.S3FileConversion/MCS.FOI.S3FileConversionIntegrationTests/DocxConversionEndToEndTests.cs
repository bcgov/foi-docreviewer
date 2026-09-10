using System.Diagnostics;
using System.Net;
using System.Text;
using System.Text.Json;
using Amazon.Runtime;
using Amazon.S3;
using Amazon.S3.Model;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using Npgsql;
using StackExchange.Redis;

namespace MCS.FOI.S3FileConversionIntegrationTests;

[TestClass]
[TestCategory("Integration")]
[DoNotParallelize]
public sealed class DocxConversionEndToEndTests
{
    private static readonly TimeSpan Deadline = TimeSpan.FromSeconds(60);
    private const string SourceFileName = "simple-test-doc.docx";
    private const string SourceKey = "requests/FOI-TEST-001/simple-test-doc.docx";
    private const string PdfKey = "requests/FOI-TEST-001/simple-test-doc.pdf";
    private const string SourceUrl = "http://seaweedfs:8333/integration-bucket/" + SourceKey;
    private const string PdfUrl = "http://seaweedfs:8333/integration-bucket/" + PdfKey;

    [TestMethod]
    public async Task ConvertsDocxAndPublishesDedupeWork()
    {
        if (string.IsNullOrWhiteSpace(
                Environment.GetEnvironmentVariable("DATABASE_CONNECTION_STRING")))
        {
            Assert.Inconclusive(
                "Run this integration test through ./integration/run.sh");
        }

        var settings = IntegrationSettings.FromEnvironment();
        var artifacts = IntegrationArtifactWriter.FromEnvironment("docx");
        artifacts.Reset();
        await artifacts.CopyAsync(FixturePath(), "original", SourceFileName);
        var scenario = Stopwatch.StartNew();
        await using var postgres = new NpgsqlConnection(settings.DatabaseConnectionString);
        await postgres.OpenAsync();
        await using var redis = await ConnectionMultiplexer.ConnectAsync(settings.RedisConnectionString);
        var db = redis.GetDatabase();
        using var s3 = CreateS3Client(settings);

        await CreateBucketAndUploadFixture(s3, settings);
        await SeedDatabase(postgres, settings);
        await WaitForConsumerGroup(db, settings, Remaining(scenario));
        var baselineDedupeCount = await db.StreamLengthAsync(settings.DedupeStream);
        var inputId = await PublishConversionJob(db, settings);
        var completed = await WaitForCompletion(postgres, Remaining(scenario));

        await SaveObject(
            s3,
            settings,
            PdfKey,
            artifacts,
            "converted",
            "simple-test-doc.pdf");
        await AssertObjectStorage(s3, settings);
        var dedupeJob = await AssertDatabase(postgres, completed);
        await WaitForDownstream(
            db,
            settings,
            baselineDedupeCount,
            expectedNewDedupeCount: 1,
            Remaining(scenario));
        await AssertDedupeEvent(db, settings, completed, dedupeJob);
        await AssertAcknowledged(db, settings, inputId);
    }

    private static TimeSpan Remaining(Stopwatch scenario)
    {
        var remaining = Deadline - scenario.Elapsed;
        if (remaining <= TimeSpan.Zero)
        {
            throw new AssertFailedException(
                $"Integration scenario exceeded its {Deadline.TotalSeconds}-second deadline");
        }

        return remaining;
    }

    private static AmazonS3Client CreateS3Client(IntegrationSettings settings)
    {
        var config = new AmazonS3Config
        {
            ServiceURL = settings.S3Endpoint,
            ForcePathStyle = true,
            AuthenticationRegion = "us-east-1"
        };
        return new AmazonS3Client(
            new BasicAWSCredentials(settings.S3AccessKey, settings.S3SecretKey),
            config);
    }

    private static async Task CreateBucketAndUploadFixture(
        IAmazonS3 s3,
        IntegrationSettings settings)
    {
        try
        {
            await s3.PutBucketAsync(new PutBucketRequest { BucketName = settings.S3Bucket });
        }
        catch (AmazonS3Exception exception) when (
            exception.StatusCode == HttpStatusCode.Conflict ||
            exception.ErrorCode is "BucketAlreadyExists" or "BucketAlreadyOwnedByYou")
        {
            // A rerun against a live diagnostic stack may reuse the bucket.
        }

        var fixture = FixturePath();
        Assert.IsTrue(File.Exists(fixture), $"DOCX fixture not found at {fixture}");
        await using var stream = File.OpenRead(fixture);
        await s3.PutObjectAsync(new PutObjectRequest
        {
            BucketName = settings.S3Bucket,
            Key = SourceKey,
            InputStream = stream,
            ContentType = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        });
    }

    private static string FixturePath() =>
        Path.Combine(AppContext.BaseDirectory, "Fixtures", SourceFileName);

    private static async Task SaveObject(
        IAmazonS3 s3,
        IntegrationSettings settings,
        string key,
        IntegrationArtifactWriter artifacts,
        params string[] relativePath)
    {
        using var response = await s3.GetObjectAsync(settings.S3Bucket, key);
        await artifacts.WriteAsync(response.ResponseStream, relativePath);
    }

    private static async Task SeedDatabase(
        NpgsqlConnection postgres,
        IntegrationSettings settings)
    {
        const string sql = """
            INSERT INTO "DocumentPathMapper"
                (category, bucket, attributes, isactive, createdby)
            VALUES
                ('integration', @bucket, '{"s3accesskey":"dev","s3secretkey":"dev"}', true, 'integration-test');

            INSERT INTO "DocumentMaster"
                (documentmasterid, filepath, ministryrequestid, isredactionready, createdby)
            VALUES
                (3001, @sourceUrl, 1001, false, 'integration-test');

            INSERT INTO "FileConversionJob"
                (fileconversionjobid, version, ministryrequestid, batch, trigger,
                 inputdocumentmasterid, filename, status)
            VALUES
                (2001, 1, 1001, 'batch-integration-001', 'recordupload',
                 3001, 'simple-test-doc.docx', 'pushedtostream');
            """;

        await using var command = new NpgsqlCommand(sql, postgres);
        command.Parameters.AddWithValue("bucket", settings.S3Bucket);
        command.Parameters.AddWithValue("sourceUrl", SourceUrl);
        await command.ExecuteNonQueryAsync();
    }

    private static async Task WaitForConsumerGroup(
        IDatabase db,
        IntegrationSettings settings,
        TimeSpan deadline)
    {
        var stopwatch = Stopwatch.StartNew();
        while (stopwatch.Elapsed < deadline)
        {
            try
            {
                var groups = await db.StreamGroupInfoAsync(settings.ConversionStream);
                if (groups.Any(group => group.Name == settings.ConsumerGroup))
                {
                    return;
                }
            }
            catch (RedisServerException exception) when (
                exception.Message.Contains("no such key", StringComparison.OrdinalIgnoreCase))
            {
                // The worker creates both the stream and group during startup.
            }

            await Task.Delay(TimeSpan.FromMilliseconds(200));
        }

        throw new AssertFailedException(
            $"Consumer group {settings.ConsumerGroup} was not created within {deadline.TotalSeconds} seconds");
    }

    private static async Task<RedisValue> PublishConversionJob(
        IDatabase db,
        IntegrationSettings settings)
    {
        const string attributes = """{"filesize":12536,"extension":".docx"}""";
        return await db.StreamAddAsync(
            settings.ConversionStream,
            [
                new NameValueEntry("s3filepath", SourceUrl),
                new NameValueEntry("requestnumber", "FOI-TEST-001"),
                new NameValueEntry("bcgovcode", "CITZ"),
                new NameValueEntry("filename", "simple-test-doc.docx"),
                new NameValueEntry("ministryrequestid", "1001"),
                new NameValueEntry("attributes", attributes),
                new NameValueEntry("batch", "batch-integration-001"),
                new NameValueEntry("jobid", "2001"),
                new NameValueEntry("documentmasterid", "3001"),
                new NameValueEntry("trigger", "recordupload"),
                new NameValueEntry("createdby", "integration-test"),
                new NameValueEntry("usertoken", "NON_SECRET_INTEGRATION_TOKEN")
            ]);
    }

    private static async Task<CompletedConversion> WaitForCompletion(
        NpgsqlConnection postgres,
        TimeSpan deadline)
    {
        var stopwatch = Stopwatch.StartNew();
        var lastObserved = "none";
        while (stopwatch.Elapsed < deadline)
        {
            const string sql = """
                SELECT version, status, message, outputdocumentmasterid
                FROM "FileConversionJob"
                WHERE fileconversionjobid = 2001
                ORDER BY version;
                """;
            await using var command = new NpgsqlCommand(sql, postgres);
            await using var reader = await command.ExecuteReaderAsync();
            var versions = new List<string>();
            CompletedConversion? completed = null;
            while (await reader.ReadAsync())
            {
                var version = reader.GetInt32(0);
                var status = reader.GetString(1);
                var message = reader.IsDBNull(2) ? null : reader.GetString(2);
                versions.Add($"{version}:{status}");
                if (version == 3 && status == "error")
                {
                    throw new AssertFailedException(
                        $"Conversion job 2001 failed: {message ?? "no error message"}");
                }

                if (version == 3 && status == "completed")
                {
                    Assert.IsFalse(reader.IsDBNull(3), "Completed job has no output document ID");
                    completed = new CompletedConversion(reader.GetInt32(3));
                }
            }

            lastObserved = string.Join(", ", versions);
            if (completed is not null)
            {
                return completed;
            }

            await Task.Delay(TimeSpan.FromMilliseconds(200));
        }

        throw new AssertFailedException(
            $"Conversion did not complete within {deadline.TotalSeconds} seconds; last job versions: {lastObserved}");
    }

    private static async Task AssertObjectStorage(
        IAmazonS3 s3,
        IntegrationSettings settings)
    {
        await s3.GetObjectMetadataAsync(settings.S3Bucket, SourceKey);
        using var response = await s3.GetObjectAsync(settings.S3Bucket, PdfKey);
        await using var pdfStream = new MemoryStream();
        await response.ResponseStream.CopyToAsync(pdfStream);
        var pdf = pdfStream.ToArray();

        Assert.IsTrue(pdf.Length > 100, $"Converted PDF was only {pdf.Length} bytes");
        Assert.AreEqual("%PDF-", Encoding.ASCII.GetString(pdf, 0, 5));
        var end = pdf.Length;
        while (end > 0 && char.IsWhiteSpace((char)pdf[end - 1]))
        {
            end--;
        }

        Assert.IsTrue(
            Encoding.ASCII.GetString(pdf, 0, end).EndsWith("%%EOF", StringComparison.Ordinal),
            "Converted file does not end with a PDF EOF marker");
    }

    private static async Task<DedupeJob> AssertDatabase(
        NpgsqlConnection postgres,
        CompletedConversion completed)
    {
        const string jobsSql = """
            SELECT version, status
            FROM "FileConversionJob"
            WHERE fileconversionjobid = 2001
            ORDER BY version;
            """;
        await using (var command = new NpgsqlCommand(jobsSql, postgres))
        await using (var reader = await command.ExecuteReaderAsync())
        {
            var actual = new List<string>();
            while (await reader.ReadAsync())
            {
                actual.Add($"{reader.GetInt32(0)}:{reader.GetString(1)}");
            }

            CollectionAssert.AreEqual(
                new[] { "1:pushedtostream", "2:started", "3:completed" },
                actual);
        }

        const string outputSql = """
            SELECT filepath, processingparentid
            FROM "DocumentMaster"
            WHERE documentmasterid = @outputId;
            """;
        await using (var command = new NpgsqlCommand(outputSql, postgres))
        {
            command.Parameters.AddWithValue("outputId", completed.OutputDocumentId);
            await using var reader = await command.ExecuteReaderAsync();
            Assert.IsTrue(await reader.ReadAsync(), "Output document row was not created");
            Assert.AreEqual(PdfUrl, reader.GetString(0));
            Assert.AreEqual(3001, reader.GetInt32(1));
            Assert.IsFalse(await reader.ReadAsync(), "More than one output document row matched");
        }

        const string dedupeSql = """
            SELECT deduplicationjobid, documentmasterid, ministryrequestid, batch,
                   trigger, filename, version, status
            FROM "DeduplicationJob"
            WHERE ministryrequestid = 1001
              AND batch = 'batch-integration-001';
            """;
        await using (var command = new NpgsqlCommand(dedupeSql, postgres))
        await using (var reader = await command.ExecuteReaderAsync())
        {
            Assert.IsTrue(await reader.ReadAsync(), "Deduplication job was not created");
            var job = new DedupeJob(reader.GetInt32(0));
            Assert.AreEqual(3001, reader.GetInt32(1));
            Assert.AreEqual(1001, reader.GetInt32(2));
            Assert.AreEqual("batch-integration-001", reader.GetString(3));
            Assert.AreEqual("recordupload", reader.GetString(4));
            Assert.AreEqual("simple-test-doc.docx", reader.GetString(5));
            Assert.AreEqual(1, reader.GetInt32(6));
            Assert.AreEqual("pushedtostream", reader.GetString(7));
            Assert.IsFalse(await reader.ReadAsync(), "More than one deduplication job was created");
            return job;
        }
    }

    private static async Task WaitForDownstream(
        IDatabase db,
        IntegrationSettings settings,
        long baselineDedupeCount,
        long expectedNewDedupeCount,
        TimeSpan deadline)
    {
        var stopwatch = Stopwatch.StartNew();
        var lastObserved = "dedupe entries: unknown; pending messages: unknown";
        while (stopwatch.Elapsed < deadline)
        {
            var entries = await db.StreamRangeAsync(settings.DedupeStream);
            var pending = await db.StreamPendingAsync(
                settings.ConversionStream,
                settings.ConsumerGroup);
            lastObserved =
                $"dedupe entries: {entries.Length}; pending messages: {pending.PendingMessageCount}";

            if (DownstreamReadiness.HasSettled(
                    baselineDedupeCount,
                    entries.Length,
                    expectedNewDedupeCount,
                    pending.PendingMessageCount))
            {
                return;
            }

            await Task.Delay(TimeSpan.FromMilliseconds(200));
        }

        throw new AssertFailedException(
            $"Downstream work did not settle within {deadline.TotalSeconds:F1} seconds; {lastObserved}");
    }

    private static async Task AssertDedupeEvent(
        IDatabase db,
        IntegrationSettings settings,
        CompletedConversion completed,
        DedupeJob dedupeJob)
    {
        var matchingEntries = (await db.StreamRangeAsync(settings.DedupeStream))
            .Where(entry => entry.Values.Any(field =>
                field.Name == "requestnumber" && field.Value == "FOI-TEST-001"))
            .ToArray();
        Assert.AreEqual(1, matchingEntries.Length, "Expected one DOCX dedupe stream entry");
        var fields = matchingEntries[0].Values.ToDictionary(
            entry => entry.Name.ToString(),
            entry => entry.Value.ToString());

        Assert.AreEqual(PdfUrl, fields["s3filepath"]);
        Assert.AreEqual("FOI-TEST-001", fields["requestnumber"]);
        Assert.AreEqual("CITZ", fields["bcgovcode"]);
        Assert.AreEqual("simple-test-doc.docx", fields["filename"]);
        Assert.AreEqual("1001", fields["ministryrequestid"]);
        Assert.AreEqual("batch-integration-001", fields["batch"]);
        Assert.AreEqual(dedupeJob.Id.ToString(), fields["jobid"]);
        Assert.AreEqual("3001", fields["documentmasterid"]);
        Assert.AreEqual(completed.OutputDocumentId.ToString(), fields["outputdocumentmasterid"]);
        Assert.AreEqual("recordupload", fields["trigger"]);
        Assert.AreEqual("integration-test", fields["createdby"]);
        Assert.AreEqual("NON_SECRET_INTEGRATION_TOKEN", fields["usertoken"]);

        using var attributes = JsonDocument.Parse(fields["attributes"]);
        Assert.IsTrue(
            attributes.RootElement.GetProperty("convertedfilesize").GetInt64() > 0,
            "convertedfilesize must be a positive number");
    }

    private static async Task AssertAcknowledged(
        IDatabase db,
        IntegrationSettings settings,
        RedisValue inputId)
    {
        var pending = await db.StreamPendingAsync(
            settings.ConversionStream,
            settings.ConsumerGroup);
        Assert.AreEqual(
            0L,
            pending.PendingMessageCount,
            $"Input stream entry {inputId} remains pending");
    }

    private sealed record CompletedConversion(int OutputDocumentId);
    private sealed record DedupeJob(int Id);
}
