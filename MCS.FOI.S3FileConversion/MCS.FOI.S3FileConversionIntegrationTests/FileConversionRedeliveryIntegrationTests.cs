using MCS.FOI.S3FileConversion;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using Npgsql;
using StackExchange.Redis;

namespace MCS.FOI.S3FileConversionIntegrationTests;

[TestClass]
[TestCategory("Integration")]
[DoNotParallelize]
public sealed class FileConversionRedeliveryIntegrationTests
{
    private const int JobId = 2201;
    private const int DocumentMasterId = 3201;
    private const int MinistryRequestId = 1201;

    [TestMethod]
    public async Task FailedJobWritesCanBeRepeatedAndThenCompleted()
    {
        if (string.IsNullOrWhiteSpace(
                Environment.GetEnvironmentVariable("DATABASE_CONNECTION_STRING")))
        {
            Assert.Inconclusive("Run this integration test through ./integration/run.sh");
        }

        var settings = IntegrationSettings.FromEnvironment();
        await using var postgres = new NpgsqlConnection(settings.DatabaseConnectionString);
        await postgres.OpenAsync();
        await SeedDatabase(postgres);
        var message = Message();

        using var database = new DBHandler();
        await database.recordJobStart(message);
        await database.recordJobEnd(
            message,
            true,
            "first conversion failed",
            new List<Dictionary<string, string>>());

        await database.recordJobStart(message);
        using var competingDatabase = new DBHandler();
        var completions = await Task.WhenAll(
            database.recordJobEnd(
                message,
                false,
                "",
                new List<Dictionary<string, string>>()),
            competingDatabase.recordJobEnd(
                message,
                false,
                "",
                new List<Dictionary<string, string>>()));
        var firstCompletion = completions[0];
        var competingCompletion = completions[1];
        var repeatedCompletion = await database.recordJobEnd(
            message,
            false,
            "",
            new List<Dictionary<string, string>>());
        await database.recordJobEnd(
            message,
            true,
            "late failure after completion",
            new List<Dictionary<string, string>>());

        CollectionAssert.AreEqual(
            new[] { "1:pushedtostream", "2:started", "3:completed" },
            await JobVersions(postgres));
        Assert.AreEqual(
            firstCompletion.Single().Value["jobID"],
            repeatedCompletion.Single().Value["jobID"]);
        Assert.AreEqual(
            firstCompletion.Single().Value["masterID"],
            repeatedCompletion.Single().Value["masterID"]);
        Assert.AreEqual(
            firstCompletion.Single().Value["jobID"],
            competingCompletion.Single().Value["jobID"]);
        Assert.AreEqual(
            firstCompletion.Single().Value["masterID"],
            competingCompletion.Single().Value["masterID"]);
        CollectionAssert.AreEqual(
            new[] { 1, 1 },
            await CompletionSideEffectCounts(postgres));
    }

    private static async Task SeedDatabase(NpgsqlConnection postgres)
    {
        const string sql = """
            INSERT INTO "DocumentMaster"
                (documentmasterid, filepath, ministryrequestid, isredactionready, createdby)
            VALUES
                (@documentMasterId, @sourceUrl, @ministryRequestId, false,
                 'integration-test');

            INSERT INTO "FileConversionJob"
                (fileconversionjobid, version, ministryrequestid, batch, trigger,
                 inputdocumentmasterid, filename, status)
            VALUES
                (@jobId, 1, @ministryRequestId, 'batch-redelivery', 'recordupload',
                 @documentMasterId, 'redelivery.docx', 'pushedtostream');

            CREATE OR REPLACE FUNCTION delay_redelivery_dedupe_insert()
            RETURNS trigger AS $$
            BEGIN
                PERFORM pg_sleep(0.25);
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            CREATE TRIGGER delay_redelivery_dedupe_insert
            BEFORE INSERT ON "DeduplicationJob"
            FOR EACH ROW
            WHEN (NEW.documentmasterid = 3201)
            EXECUTE FUNCTION delay_redelivery_dedupe_insert();
            """;

        await using var command = new NpgsqlCommand(sql, postgres);
        command.Parameters.AddWithValue("documentMasterId", DocumentMasterId);
        command.Parameters.AddWithValue(
            "sourceUrl",
            "http://seaweedfs:8333/integration-bucket/redelivery.docx");
        command.Parameters.AddWithValue("ministryRequestId", MinistryRequestId);
        command.Parameters.AddWithValue("jobId", JobId);
        await command.ExecuteNonQueryAsync();
    }

    private static StreamEntry Message() =>
        new(
            "redelivery-1-0",
            [
                new NameValueEntry(
                    "s3filepath",
                    "http://seaweedfs:8333/integration-bucket/redelivery.docx"),
                new NameValueEntry("ministryrequestid", MinistryRequestId),
                new NameValueEntry("batch", "batch-redelivery"),
                new NameValueEntry("jobid", JobId),
                new NameValueEntry("documentmasterid", DocumentMasterId),
                new NameValueEntry("trigger", "recordupload"),
                new NameValueEntry("filename", "redelivery.docx")
            ]);

    private static async Task<string[]> JobVersions(NpgsqlConnection postgres)
    {
        const string sql = """
            SELECT version, status
            FROM "FileConversionJob"
            WHERE fileconversionjobid = @jobId
            ORDER BY version;
            """;
        await using var command = new NpgsqlCommand(sql, postgres);
        command.Parameters.AddWithValue("jobId", JobId);
        await using var reader = await command.ExecuteReaderAsync();
        var versions = new List<string>();
        while (await reader.ReadAsync())
        {
            versions.Add($"{reader.GetInt32(0)}:{reader.GetString(1)}");
        }

        return versions.ToArray();
    }

    private static async Task<int[]> CompletionSideEffectCounts(
        NpgsqlConnection postgres)
    {
        const string sql = """
            SELECT
                (SELECT count(*)
                 FROM "DocumentMaster"
                 WHERE processingparentid = @documentMasterId),
                (SELECT count(*)
                 FROM "DeduplicationJob"
                 WHERE documentmasterid = @documentMasterId);
            """;
        await using var command = new NpgsqlCommand(sql, postgres);
        command.Parameters.AddWithValue("documentMasterId", DocumentMasterId);
        await using var reader = await command.ExecuteReaderAsync();
        await reader.ReadAsync();
        return [reader.GetInt32(0), reader.GetInt32(1)];
    }
}
