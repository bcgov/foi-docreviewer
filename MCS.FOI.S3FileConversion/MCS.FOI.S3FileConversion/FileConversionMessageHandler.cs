using System.Diagnostics;
using System.Text.Json;
using System.Text.Json.Nodes;
using MCS.FOI.S3FileConversion.Messaging;
using MCS.FOI.S3FileConversion.Utilities;
using Serilog;
using Serilog.Context;
using StackExchange.Redis;

namespace MCS.FOI.S3FileConversion;

public sealed class FileConversionMessageHandler : IStreamMessageHandler
{
    private readonly IDatabase database;
    private readonly RedisKey conversionStream;
    private readonly RedisKey dedupeStream;

    public FileConversionMessageHandler(
        IDatabase database,
        string conversionStream,
        string dedupeStream)
    {
        this.database = database;
        this.conversionStream = conversionStream;
        this.dedupeStream = dedupeStream;
    }

    public async Task<MessageHandlingResult> HandleAsync(
        StreamEntry message,
        CancellationToken cancellationToken)
    {
        try
        {
            ValidateMessage(message);
        }
        catch (MissingFieldException error)
        {
            Log.Warning(error, "Job rejected because a required field is missing");
            return MessageHandlingResult.Permanent(error);
        }

        using var requestNumber = LogContext.PushProperty(
            "RequestNumber", message["requestnumber"].ToString());
        using var bcGovCode = LogContext.PushProperty(
            "BCGovCode", message["bcgovcode"].ToString());
        using var ministryRequestId = LogContext.PushProperty(
            "MinistryRequestId", message["ministryrequestid"].ToString());
        using var jobId = LogContext.PushProperty("JobId", message["jobid"].ToString());
        using var filename = LogContext.PushProperty("Filename", message["filename"].ToString());
        using var filepath = LogContext.PushProperty("Filepath", message["s3filepath"].ToString());
        using var dbHandler = new DBHandler();

        try
        {
            await ProcessConversionAsync(message, dbHandler, cancellationToken);
            return MessageHandlingResult.Succeeded();
        }
        catch (Exception error)
        {
            Log.Error(error, "Error converting file");
            try
            {
                var jobMessage = $"Error converting {message["s3filepath"]}: {error.Message}";
                await dbHandler.recordJobEnd(
                    message,
                    true,
                    jobMessage,
                    new List<Dictionary<string, string>>());
            }
            catch (Exception recordError)
            {
                Log.Error(
                    recordError,
                    "Unable to record failed conversion job {JobId}",
                    message["jobid"].ToString());
            }

            return MessageHandlingResult.Retryable(error);
        }
    }

    internal static void ValidateMessage(StreamEntry message)
    {
        Require(message, "s3filepath");
        Require(message, "requestnumber");
        Require(message, "bcgovcode");
        Require(message, "filename");
        Require(message, "ministryrequestid");
        Require(message, "attributes");
        Require(message, "batch");
        Require(message, "jobid");
        Require(message, "documentmasterid");
        Require(message, "trigger");
        Require(message, "createdby");
        Require(message, "usertoken");
    }

    private async Task ProcessConversionAsync(
        StreamEntry message,
        DBHandler dbHandler,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        await dbHandler.recordJobStart(message);
        Log.Information("Job started");

        using var s3Handler = new S3Handler();
        var filePath = message["s3filepath"].ToString();
        var bucket = filePath.Split('/')[3];
        var s3AccessKeys = await dbHandler.getAccessKeyFromDB(bucket);
        cancellationToken.ThrowIfCancellationRequested();

        var stopwatch = Stopwatch.StartNew();
        var (attachments, convertedSize) = await s3Handler.ConvertFile(message, s3AccessKeys);
        stopwatch.Stop();
        Log.Information(
            "File conversion completed in {Duration}ms",
            stopwatch.Elapsed.TotalMilliseconds);

        cancellationToken.ThrowIfCancellationRequested();
        var jobIds = await dbHandler.recordJobEnd(message, false, "", attachments);
        if (attachments is { Count: > 0 })
        {
            foreach (var attachment in attachments)
            {
                var attributesDictionary = JsonSerializer.Deserialize<Dictionary<string, object>>(
                    attachment["attributes"])!;
                var incompatible = attributesDictionary.TryGetValue("incompatible", out var value)
                    ? value.ToString()!.ToLowerInvariant()
                    : "false";

                if (Array.IndexOf(
                        ConversionSettings.ConversionFormats,
                        attachment["extension"].ToLowerInvariant()) == -1)
                {
                    database.StreamAdd(dedupeStream, new NameValueEntry[]
                    {
                        new("s3filepath", attachment["filepath"]),
                        new("requestnumber", message["requestnumber"]),
                        new("bcgovcode", message["bcgovcode"]),
                        new("filename", attachment["filename"]),
                        new("ministryrequestid", message["ministryrequestid"]),
                        new("attributes", attachment["attributes"]),
                        new("batch", message["batch"]),
                        new("jobid", jobIds[attachment["filepath"]]["jobID"]),
                        new("documentmasterid", jobIds[attachment["filepath"]]["masterID"]),
                        new("incompatible", incompatible),
                        new("trigger", "attachment"),
                        new("createdby", message["createdby"]),
                        new("usertoken", message["usertoken"])
                    });
                    Log.Information(
                        "Queued attachment to DEDUPE STREAM {TargetStream}: {AttachmentFilename} ({AttachmentExtension})",
                        dedupeStream,
                        attachment["filename"],
                        attachment["extension"]);
                }
                else
                {
                    database.StreamAdd(conversionStream, new NameValueEntry[]
                    {
                        new("s3filepath", attachment["filepath"]),
                        new("requestnumber", message["requestnumber"]),
                        new("bcgovcode", message["bcgovcode"]),
                        new("filename", attachment["filename"]),
                        new("ministryrequestid", message["ministryrequestid"]),
                        new("attributes", attachment["attributes"]),
                        new("batch", message["batch"]),
                        new("parentfilepath", message["s3filepath"]),
                        new("parentfilename", message["filename"]),
                        new("jobid", jobIds[attachment["filepath"]]["jobID"]),
                        new("documentmasterid", jobIds[attachment["filepath"]]["masterID"]),
                        new("trigger", "attachment"),
                        new("createdby", message["createdby"]),
                        new("usertoken", message["usertoken"])
                    });
                    Log.Information(
                        "Queued attachment to CONVERSION STREAM {TargetStream}: {AttachmentFilename} ({AttachmentExtension})",
                        conversionStream,
                        attachment["filename"],
                        attachment["extension"]);
                }
            }
        }

        cancellationToken.ThrowIfCancellationRequested();
        var newFilename = Path.ChangeExtension(message["s3filepath"].ToString(), ".pdf");
        var attributes = JsonSerializer.Deserialize<JsonNode>(message["attributes"].ToString())!;
        attributes["convertedfilesize"] = JsonValue.Create(convertedSize);
        database.StreamAdd(dedupeStream, new NameValueEntry[]
        {
            new("s3filepath", newFilename),
            new("requestnumber", message["requestnumber"]),
            new("bcgovcode", message["bcgovcode"]),
            new("filename", message["filename"]),
            new("ministryrequestid", message["ministryrequestid"]),
            new("attributes", attributes.ToJsonString()),
            new("batch", message["batch"]),
            new("jobid", jobIds[newFilename]["jobID"]),
            new("documentmasterid", message["documentmasterid"]),
            new("outputdocumentmasterid", jobIds[newFilename]["masterID"]),
            new("trigger", message["trigger"]),
            new("createdby", message["createdby"]),
            new("usertoken", message["usertoken"])
        });
        Log.Information("Queued converted file to DEDUPE STREAM {TargetStream}", dedupeStream);
        Log.Information("Job completed successfully");
    }

    private static void Require(StreamEntry message, string field)
    {
        if (message[field].IsNull)
        {
            throw new MissingFieldException($"Redis stream message missing field '{field}'");
        }
    }
}
