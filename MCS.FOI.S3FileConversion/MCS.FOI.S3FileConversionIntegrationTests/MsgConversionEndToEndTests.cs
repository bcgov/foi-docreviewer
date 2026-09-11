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
public sealed class MsgConversionEndToEndTests
{
    private static readonly TimeSpan Deadline = TimeSpan.FromSeconds(60);
    private const string RequestNumber = "FOI-TEST-MSG-001";
    private const string Batch = "batch-msg-integration-001";
    private const string SourceFileName = "Test-MSG-File-with-Attachments.msg";
    private const string SourceKey = "requests/FOI-TEST-MSG-001/" + SourceFileName;
    private const string PdfKey = "requests/FOI-TEST-MSG-001/Test-MSG-File-with-Attachments.pdf";
    private const string SourceUrl = "http://seaweedfs:8333/integration-bucket/" + SourceKey;
    private const string PdfUrl = "http://seaweedfs:8333/integration-bucket/" + PdfKey;

    [TestMethod]
    public async Task ConvertsMsgAndRoutesExtractedAttachments()
    {
        if (string.IsNullOrWhiteSpace(
                Environment.GetEnvironmentVariable("DATABASE_CONNECTION_STRING")))
        {
            Assert.Inconclusive(
                "Run this integration test through ./integration/run.sh");
        }

        var settings = IntegrationSettings.FromEnvironment();
        var artifacts = IntegrationArtifactWriter.FromEnvironment("msg");
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

        await WaitForDownstream(
            postgres,
            db,
            settings,
            baselineDedupeCount,
            Remaining(scenario));

        var state = await LoadDatabaseState(postgres);
        await SaveArtifacts(s3, settings, state, artifacts);
        await AssertStorageAndDatabase(s3, settings, state);
        await AssertRedisRouting(db, settings, state);
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
            // A second scenario or rerun against a live stack may reuse the bucket.
        }

        var fixture = FixturePath();
        Assert.IsTrue(File.Exists(fixture), $"MSG fixture not found at {fixture}");
        await using var stream = File.OpenRead(fixture);
        await s3.PutObjectAsync(new PutObjectRequest
        {
            BucketName = settings.S3Bucket,
            Key = SourceKey,
            InputStream = stream,
            ContentType = "application/vnd.ms-outlook"
        });
    }

    private static string FixturePath() =>
        Path.Combine(AppContext.BaseDirectory, "Fixtures", SourceFileName);

    private static async Task SaveArtifacts(
        IAmazonS3 s3,
        IntegrationSettings settings,
        DatabaseState state,
        IntegrationArtifactWriter artifacts)
    {
        await SaveObject(
            s3,
            settings,
            PdfKey,
            artifacts,
            "converted",
            "Test-MSG-File-with-Attachments.pdf");

        foreach (var attachment in state.Attachments)
        {
            var originalName = state.ConversionJobs
                .FirstOrDefault(job => job.Version == 1 && job.InputDocumentId == attachment.Id)
                ?.Filename
                ?? state.DedupeJobs.Single(job => job.DocumentId == attachment.Id).Filename;
            var artifactName = $"document-{attachment.Id}-{Path.GetFileName(originalName)}";
            await SaveObject(
                s3,
                settings,
                ObjectKey(attachment.FilePath, settings.S3Bucket),
                artifacts,
                "attachments",
                "original",
                artifactName);

            var completedConversion = state.ConversionJobs.SingleOrDefault(job =>
                job.InputDocumentId == attachment.Id && job.Version == 3);
            if (completedConversion is not null)
            {
                await SaveObject(
                    s3,
                    settings,
                    ObjectKey(Path.ChangeExtension(attachment.FilePath, ".pdf"), settings.S3Bucket),
                    artifacts,
                    "attachments",
                    "converted",
                    Path.ChangeExtension(artifactName, ".pdf"));
            }
        }
    }

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
            SELECT
                'integration', @bucket, '{"s3accesskey":"dev","s3secretkey":"dev"}', true,
                'integration-test'
            WHERE NOT EXISTS (
                SELECT 1
                FROM "DocumentPathMapper"
                WHERE bucket = @bucket AND isactive = true
            );

            INSERT INTO "DocumentMaster"
                (documentmasterid, filepath, ministryrequestid, isredactionready, createdby)
            VALUES
                (3101, @sourceUrl, 1101, false, 'integration-test');

            INSERT INTO "FileConversionJob"
                (fileconversionjobid, version, ministryrequestid, batch, trigger,
                 inputdocumentmasterid, filename, status)
            VALUES
                (2101, 1, 1101, @batch, 'recordupload',
                 3101, @filename, 'pushedtostream');
            """;

        await using var command = new NpgsqlCommand(sql, postgres);
        command.Parameters.AddWithValue("bucket", settings.S3Bucket);
        command.Parameters.AddWithValue("sourceUrl", SourceUrl);
        command.Parameters.AddWithValue("batch", Batch);
        command.Parameters.AddWithValue("filename", SourceFileName);
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
            $"Consumer group {settings.ConsumerGroup} was not created within {deadline.TotalSeconds:F1} seconds");
    }

    private static async Task<RedisValue> PublishConversionJob(
        IDatabase db,
        IntegrationSettings settings)
    {
        var attributes = JsonSerializer.Serialize(new
        {
            filesize = new FileInfo(FixturePath()).Length,
            extension = ".msg"
        });
        return await db.StreamAddAsync(
            settings.ConversionStream,
            [
                new NameValueEntry("s3filepath", SourceUrl),
                new NameValueEntry("requestnumber", RequestNumber),
                new NameValueEntry("bcgovcode", "CITZ"),
                new NameValueEntry("filename", SourceFileName),
                new NameValueEntry("ministryrequestid", "1101"),
                new NameValueEntry("attributes", attributes),
                new NameValueEntry("batch", Batch),
                new NameValueEntry("jobid", "2101"),
                new NameValueEntry("documentmasterid", "3101"),
                new NameValueEntry("trigger", "recordupload"),
                new NameValueEntry("createdby", "integration-test"),
                new NameValueEntry("usertoken", "NON_SECRET_INTEGRATION_TOKEN")
            ]);
    }

    private static async Task WaitForDownstream(
        NpgsqlConnection postgres,
        IDatabase db,
        IntegrationSettings settings,
        long baselineDedupeCount,
        TimeSpan deadline)
    {
        var stopwatch = Stopwatch.StartNew();
        var lastObserved = "dedupe entries: unknown; pending messages: unknown; jobs: unknown";
        while (stopwatch.Elapsed < deadline)
        {
            var jobs = await LoadConversionJobs(postgres);
            var failed = jobs.FirstOrDefault(job => job.Version == 3 && job.Status == "error");
            if (failed is not null)
            {
                throw new AssertFailedException(
                    $"Conversion failed for {failed.Filename}: {failed.Message ?? "no error message"}");
            }

            var dedupeCount = await db.StreamLengthAsync(settings.DedupeStream);
            var pending = await db.StreamPendingAsync(
                settings.ConversionStream,
                settings.ConsumerGroup);
            var parentCompleted = jobs.Any(job =>
                job.Id == 2101 && job.Version == 3 && job.Status == "completed");
            var attachmentCount = parentCompleted
                ? (await LoadAttachmentDocuments(postgres)).Count
                : 0;
            var expectedNewDedupeCount = attachmentCount + 1L;
            var jobVersions = string.Join(
                ", ",
                jobs.Select(job => $"{job.Id}/{job.Filename}/{job.Version}:{job.Status}"));
            lastObserved =
                $"dedupe entries: {dedupeCount} (baseline {baselineDedupeCount}); " +
                $"expected new entries: {(parentCompleted ? expectedNewDedupeCount : null)}; " +
                $"attachments: {(parentCompleted ? attachmentCount : null)}; " +
                $"pending messages: {pending.PendingMessageCount}; jobs: {jobVersions}";

            if (parentCompleted && DownstreamReadiness.HasSettled(
                    baselineDedupeCount,
                    dedupeCount,
                    expectedNewDedupeCount,
                    pending.PendingMessageCount))
            {
                return;
            }

            await Task.Delay(TimeSpan.FromMilliseconds(200));
        }

        throw new AssertFailedException(
            $"MSG downstream work did not settle within {deadline.TotalSeconds:F1} seconds; {lastObserved}");
    }

    private static async Task<DatabaseState> LoadDatabaseState(NpgsqlConnection postgres)
    {
        var jobs = await LoadConversionJobs(postgres);
        var attachments = await LoadAttachmentDocuments(postgres);
        var attributes = await LoadAttachmentAttributes(postgres);
        var dedupeJobs = await LoadDedupeJobs(postgres);
        return new DatabaseState(jobs, attachments, attributes, dedupeJobs);
    }

    private static async Task<List<ConversionJob>> LoadConversionJobs(
        NpgsqlConnection postgres)
    {
        const string sql = """
            SELECT fileconversionjobid, version, status, filename, message,
                   inputdocumentmasterid, outputdocumentmasterid, trigger
            FROM "FileConversionJob"
            WHERE ministryrequestid = 1101 AND batch = @batch
            ORDER BY fileconversionjobid, version;
            """;
        await using var command = new NpgsqlCommand(sql, postgres);
        command.Parameters.AddWithValue("batch", Batch);
        await using var reader = await command.ExecuteReaderAsync();
        var jobs = new List<ConversionJob>();
        while (await reader.ReadAsync())
        {
            jobs.Add(new ConversionJob(
                reader.GetInt32(0),
                reader.GetInt32(1),
                reader.GetString(2),
                reader.GetString(3),
                reader.IsDBNull(4) ? null : reader.GetString(4),
                reader.GetInt32(5),
                reader.IsDBNull(6) ? null : reader.GetInt32(6),
                reader.GetString(7)));
        }

        return jobs;
    }

    private static async Task<List<AttachmentDocument>> LoadAttachmentDocuments(
        NpgsqlConnection postgres)
    {
        const string sql = """
            SELECT documentmasterid, filepath, parentid
            FROM "DocumentMaster"
            WHERE parentid = 3101
            ORDER BY filepath;
            """;
        await using var command = new NpgsqlCommand(sql, postgres);
        await using var reader = await command.ExecuteReaderAsync();
        var documents = new List<AttachmentDocument>();
        while (await reader.ReadAsync())
        {
            documents.Add(new AttachmentDocument(
                reader.GetInt32(0),
                reader.GetString(1),
                reader.GetInt32(2)));
        }

        return documents;
    }

    private static async Task<Dictionary<int, JsonDocument>> LoadAttachmentAttributes(
        NpgsqlConnection postgres)
    {
        const string sql = """
            SELECT da.documentmasterid, da.attributes
            FROM "DocumentAttributes" da
            JOIN "DocumentMaster" dm ON dm.documentmasterid = da.documentmasterid
            WHERE dm.parentid = 3101 AND da.version = 1 AND da.isactive = true;
            """;
        await using var command = new NpgsqlCommand(sql, postgres);
        await using var reader = await command.ExecuteReaderAsync();
        var attributes = new Dictionary<int, JsonDocument>();
        while (await reader.ReadAsync())
        {
            attributes.Add(reader.GetInt32(0), JsonDocument.Parse(reader.GetString(1)));
        }

        return attributes;
    }

    private static async Task<List<DedupeJob>> LoadDedupeJobs(NpgsqlConnection postgres)
    {
        const string sql = """
            SELECT deduplicationjobid, version, documentmasterid, trigger, filename, status
            FROM "DeduplicationJob"
            WHERE ministryrequestid = 1101 AND batch = @batch
            ORDER BY deduplicationjobid;
            """;
        await using var command = new NpgsqlCommand(sql, postgres);
        command.Parameters.AddWithValue("batch", Batch);
        await using var reader = await command.ExecuteReaderAsync();
        var jobs = new List<DedupeJob>();
        while (await reader.ReadAsync())
        {
            jobs.Add(new DedupeJob(
                reader.GetInt32(0),
                reader.GetInt32(1),
                reader.GetInt32(2),
                reader.GetString(3),
                reader.GetString(4),
                reader.GetString(5)));
        }

        return jobs;
    }

    private static async Task AssertStorageAndDatabase(
        IAmazonS3 s3,
        IntegrationSettings settings,
        DatabaseState state)
    {
        var parentVersions = state.ConversionJobs
            .Where(job => job.Id == 2101)
            .Select(job => $"{job.Version}:{job.Status}")
            .ToArray();
        CollectionAssert.AreEqual(
            new[] { "1:pushedtostream", "2:started", "3:completed" },
            parentVersions);

        var parentCompleted = state.ConversionJobs.Single(job => job.Id == 2101 && job.Version == 3);
        Assert.IsNotNull(parentCompleted.OutputDocumentId, "Parent conversion has no output document ID");
        await AssertOutputDocument(
            parentCompleted.OutputDocumentId.Value,
            expectedPath: PdfUrl,
            expectedProcessingParentId: 3101,
            settings.DatabaseConnectionString);
        await AssertPdf(s3, settings, PdfKey);

        Assert.IsTrue(state.Attachments.Count > 0, "Expected at least one extracted attachment document");
        Assert.IsTrue(state.Attachments.All(document => document.ParentId == 3101));
        Assert.AreEqual(
            state.Attachments.Count,
            state.Attributes.Count,
            "Expected one active attribute row per attachment");

        foreach (var attachment in state.Attachments)
        {
            Assert.IsTrue(
                state.Attributes.TryGetValue(attachment.Id, out var attributes),
                $"No active attributes found for attachment document {attachment.Id}");
            var root = attributes!.RootElement;
            Assert.IsTrue(root.GetProperty("isattachment").GetBoolean());
            Assert.AreEqual(SourceUrl, root.GetProperty("rootparentfilepath").GetString());
            Assert.AreEqual(
                Path.GetExtension(attachment.FilePath),
                root.GetProperty("extension").GetString());
            Assert.IsTrue(ReadPositiveInt64(root.GetProperty("filesize")) > 0);
            Assert.IsTrue(
                root.GetProperty("incompatible").ValueKind is JsonValueKind.True or JsonValueKind.False,
                $"Attachment {attachment.Id} has a non-boolean incompatible attribute");
            var metadata = await s3.GetObjectMetadataAsync(
                settings.S3Bucket,
                ObjectKey(attachment.FilePath, settings.S3Bucket));
            Assert.IsTrue(metadata.ContentLength > 0, $"Attachment {attachment.FilePath} is empty");
        }

        foreach (var attachment in state.Attachments)
        {
            var childJobs = state.ConversionJobs
                .Where(job => job.InputDocumentId == attachment.Id)
                .OrderBy(job => job.Version)
                .ToArray();
            if (childJobs.Length == 0)
            {
                Assert.AreEqual(
                    "fileconversion",
                    state.DedupeJobs.Single(job => job.DocumentId == attachment.Id).Trigger);
                continue;
            }

            CollectionAssert.AreEqual(
                new[] { "1:pushedtostream", "2:started", "3:completed" },
                childJobs.Select(job => $"{job.Version}:{job.Status}").ToArray());
            var completed = childJobs.Single(job => job.Version == 3);
            Assert.IsNotNull(
                completed.OutputDocumentId,
                $"Attachment conversion job {completed.Id} has no output document ID");
            var pdfPath = Path.ChangeExtension(attachment.FilePath, ".pdf");
            await AssertOutputDocument(
                completed.OutputDocumentId.Value,
                pdfPath,
                attachment.Id,
                settings.DatabaseConnectionString);
            await AssertPdf(s3, settings, ObjectKey(pdfPath, settings.S3Bucket));
            Assert.AreEqual(
                "attachment",
                state.DedupeJobs.Single(job => job.DocumentId == attachment.Id).Trigger);
        }

        Assert.AreEqual(
            state.Attachments.Count + 1,
            state.DedupeJobs.Count,
            "Expected one dedupe job for the parent and each attachment");
        Assert.IsTrue(state.DedupeJobs.All(job => job.Version == 1));
        Assert.IsTrue(state.DedupeJobs.All(job => job.Status == "pushedtostream"));
        Assert.AreEqual(
            1,
            state.DedupeJobs.Count(job => job.Trigger == "recordupload" && job.DocumentId == 3101));
        var attachmentDocumentIds = state.Attachments.Select(document => document.Id).ToHashSet();
        var attachmentJobs = state.DedupeJobs
            .Where(job => attachmentDocumentIds.Contains(job.DocumentId))
            .ToArray();
        Assert.AreEqual(state.Attachments.Count, attachmentJobs.Length);
        Assert.IsTrue(state.Attachments.All(attachment =>
            attachmentJobs.Count(job => job.DocumentId == attachment.Id) == 1));
    }

    private static async Task AssertOutputDocument(
        int outputDocumentId,
        string expectedPath,
        int expectedProcessingParentId,
        string connectionString)
    {
        await using var postgres = new NpgsqlConnection(connectionString);
        await postgres.OpenAsync();
        const string sql = """
            SELECT filepath, processingparentid
            FROM "DocumentMaster"
            WHERE documentmasterid = @outputId;
            """;
        await using var command = new NpgsqlCommand(sql, postgres);
        command.Parameters.AddWithValue("outputId", outputDocumentId);
        await using var reader = await command.ExecuteReaderAsync();
        Assert.IsTrue(await reader.ReadAsync(), $"Output document {outputDocumentId} was not created");
        Assert.AreEqual(expectedPath, reader.GetString(0));
        Assert.AreEqual(expectedProcessingParentId, reader.GetInt32(1));
        Assert.IsFalse(await reader.ReadAsync(), $"More than one output document matched {outputDocumentId}");
    }

    private static async Task AssertPdf(
        IAmazonS3 s3,
        IntegrationSettings settings,
        string key)
    {
        using var response = await s3.GetObjectAsync(settings.S3Bucket, key);
        await using var pdfStream = new MemoryStream();
        await response.ResponseStream.CopyToAsync(pdfStream);
        var pdf = pdfStream.ToArray();
        Assert.IsTrue(pdf.Length > 100, $"Converted PDF {key} was only {pdf.Length} bytes");
        Assert.AreEqual("%PDF-", Encoding.ASCII.GetString(pdf, 0, 5));
        var end = pdf.Length;
        while (end > 0 && char.IsWhiteSpace((char)pdf[end - 1]))
        {
            end--;
        }

        Assert.IsTrue(
            Encoding.ASCII.GetString(pdf, 0, end).EndsWith("%%EOF", StringComparison.Ordinal),
            $"Converted file {key} does not end with a PDF EOF marker");
    }

    private static async Task AssertRedisRouting(
        IDatabase db,
        IntegrationSettings settings,
        DatabaseState state)
    {
        var conversionEntries = (await db.StreamRangeAsync(settings.ConversionStream))
            .Select(Fields)
            .Where(fields => fields.GetValueOrDefault("requestnumber") == RequestNumber)
            .ToArray();
        var childEntries = conversionEntries
            .Where(fields => fields.GetValueOrDefault("trigger") == "attachment")
            .ToArray();

        var expectedChildRoutes = state.ConversionJobs
            .Where(job => job.Version == 1 && job.Trigger == "attachment")
            .Select(job =>
            {
                var attachment = state.Attachments.Single(document => document.Id == job.InputDocumentId);
                return RouteKey(job.Id, attachment.Id, attachment.FilePath, job.Filename);
            })
            .ToArray();
        Assert.AreEqual(
            expectedChildRoutes.Length,
            childEntries.Length,
            "Expected one conversion entry per convertible attachment");
        var actualChildRoutes = childEntries
            .Select(fields => RouteKey(
                int.Parse(fields["jobid"]),
                int.Parse(fields["documentmasterid"]),
                fields["s3filepath"],
                fields["filename"]))
            .ToArray();
        CollectionAssert.AreEquivalent(expectedChildRoutes, actualChildRoutes);

        foreach (var fields in childEntries)
        {
            Assert.AreEqual(SourceUrl, fields["parentfilepath"]);
            Assert.AreEqual(SourceFileName, fields["parentfilename"]);
            AssertCommonFields(fields);
        }

        var dedupeEntries = (await db.StreamRangeAsync(settings.DedupeStream))
            .Select(Fields)
            .Where(fields => fields.GetValueOrDefault("requestnumber") == RequestNumber)
            .ToArray();
        Assert.AreEqual(
            state.Attachments.Count + 1,
            dedupeEntries.Length,
            "Expected one dedupe entry for the parent and each attachment");

        var parent = dedupeEntries.Single(fields => fields["trigger"] == "recordupload");
        var parentDedupeJob = state.DedupeJobs.Single(job =>
            job.Trigger == "recordupload" && job.DocumentId == 3101);
        Assert.AreEqual(parentDedupeJob.Id.ToString(), parent["jobid"]);
        Assert.AreEqual(parentDedupeJob.DocumentId.ToString(), parent["documentmasterid"]);
        Assert.AreEqual(SourceFileName, parent["filename"]);
        Assert.AreEqual(PdfUrl, parent["s3filepath"]);
        Assert.AreEqual(
            state.ConversionJobs.Single(job => job.Id == 2101 && job.Version == 3)
                .OutputDocumentId!.Value.ToString(),
            parent["outputdocumentmasterid"]);

        var attachmentEntries = dedupeEntries
            .Where(fields => fields["trigger"] == "attachment")
            .ToArray();
        Assert.AreEqual(state.Attachments.Count, attachmentEntries.Length);
        foreach (var attachment in state.Attachments)
        {
            var fields = attachmentEntries.Single(entry =>
                entry["documentmasterid"] == attachment.Id.ToString());
            var dedupeJob = state.DedupeJobs.Single(job => job.DocumentId == attachment.Id);
            var completed = state.ConversionJobs.SingleOrDefault(job =>
                job.InputDocumentId == attachment.Id && job.Version == 3);
            Assert.AreEqual(dedupeJob.Id.ToString(), fields["jobid"]);
            Assert.AreEqual(dedupeJob.Filename, fields["filename"]);
            if (completed is null)
            {
                var incompatible = state.Attributes[attachment.Id]
                    .RootElement.GetProperty("incompatible").GetBoolean();
                Assert.AreEqual(
                    incompatible.ToString().ToLowerInvariant(),
                    fields["incompatible"]);
                Assert.AreEqual(attachment.FilePath, fields["s3filepath"]);
                Assert.IsFalse(fields.ContainsKey("outputdocumentmasterid"));
            }
            else
            {
                Assert.AreEqual(
                    Path.ChangeExtension(attachment.FilePath, ".pdf"),
                    fields["s3filepath"]);
                Assert.AreEqual(
                    completed.OutputDocumentId!.Value.ToString(),
                    fields["outputdocumentmasterid"]);
                using var attributes = JsonDocument.Parse(fields["attributes"]);
                Assert.IsTrue(
                    ReadPositiveInt64(attributes.RootElement.GetProperty("convertedfilesize")) > 0);
            }
        }

        foreach (var fields in conversionEntries.Concat(dedupeEntries))
        {
            AssertCommonFields(fields);
        }

        var pending = await db.StreamPendingAsync(
            settings.ConversionStream,
            settings.ConsumerGroup);
        Assert.AreEqual(0L, pending.PendingMessageCount);
    }

    private static void AssertCommonFields(Dictionary<string, string> fields)
    {
        Assert.AreEqual(RequestNumber, fields["requestnumber"]);
        Assert.AreEqual("1101", fields["ministryrequestid"]);
        Assert.AreEqual(Batch, fields["batch"]);
        Assert.AreEqual("integration-test", fields["createdby"]);
        Assert.AreEqual("NON_SECRET_INTEGRATION_TOKEN", fields["usertoken"]);
    }

    private static string RouteKey(int jobId, int documentId, string path, string filename) =>
        $"{jobId}|{documentId}|{path}|{filename}";

    private static Dictionary<string, string> Fields(StreamEntry entry) =>
        entry.Values.ToDictionary(field => field.Name.ToString(), field => field.Value.ToString());

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

    private static long ReadPositiveInt64(JsonElement value) =>
        value.ValueKind == JsonValueKind.String
            ? long.Parse(value.GetString()!)
            : value.GetInt64();

    private static string ObjectKey(string url, string bucket)
    {
        var path = new Uri(url).AbsolutePath.TrimStart('/');
        var prefix = bucket + "/";
        Assert.IsTrue(path.StartsWith(prefix, StringComparison.Ordinal));
        return path[prefix.Length..];
    }

    private sealed record ConversionJob(
        int Id,
        int Version,
        string Status,
        string Filename,
        string? Message,
        int InputDocumentId,
        int? OutputDocumentId,
        string Trigger);

    private sealed record AttachmentDocument(int Id, string FilePath, int ParentId);

    private sealed record DedupeJob(
        int Id,
        int Version,
        int DocumentId,
        string Trigger,
        string Filename,
        string Status);

    private sealed record DatabaseState(
        List<ConversionJob> ConversionJobs,
        List<AttachmentDocument> Attachments,
        Dictionary<int, JsonDocument> Attributes,
        List<DedupeJob> DedupeJobs);
}
