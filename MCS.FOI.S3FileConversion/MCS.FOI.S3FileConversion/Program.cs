using MCS.FOI.S3FileConversion.Utilities;
using Microsoft.Extensions.Configuration;
using Serilog;
using Serilog.Context;
using StackExchange.Redis;
using System.Diagnostics;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace MCS.FOI.S3FileConversion
{
    class Program
    {
        static async System.Threading.Tasks.Task Main(string[] args)
        {

            try
            {
                var configurationbuilder = new ConfigurationBuilder()
                        .AddJsonFile($"appsettings.json", true, true)
                        .AddEnvironmentVariables().Build();

                Log.Logger = new LoggerConfiguration()
                    .ReadFrom.Configuration(configurationbuilder)
                    .CreateLogger();

                Log.Information("MCS FOI S3FileConversion Service is up");

                //Fetching Configuration values from setting file { appsetting.{ environment_platform}.json}
                ConversionSettings.SyncfusionLicense = configurationbuilder.GetSection("ConversionSettings:SyncfusionLicense").Value;

                IConfigurationSection ministryConfigSection = configurationbuilder.GetSection("ConversionSettings:MinistryIncomingPaths");

                int.TryParse(Environment.GetEnvironmentVariable("FILE_CONVERSION_FAILTUREATTEMPT"),out int _envvarfailureAttemptCount);
                int.TryParse(configurationbuilder.GetSection("ConversionSettings:FailureAttemptCount").Value, out int failureattempt);
                ConversionSettings.FailureAttemptCount = _envvarfailureAttemptCount < 1 ? failureattempt: _envvarfailureAttemptCount;// Max. recovery attempts after a failure.

                int.TryParse(Environment.GetEnvironmentVariable("FILE_CONVERSION_WAITTIME"),out int _envvarwaitTimeInMilliSeconds);
                int.TryParse(configurationbuilder.GetSection("ConversionSettings:WaitTimeInMilliSeconds").Value, out int waittimemilliseconds);
                ConversionSettings.WaitTimeInMilliSeconds = _envvarwaitTimeInMilliSeconds == 0 ? waittimemilliseconds : _envvarwaitTimeInMilliSeconds; // Wait time between recovery attempts after a failure

                int.TryParse(configurationbuilder.GetSection("ConversionSettings:FileWatcherMonitoringDelayInMilliSeconds").Value, out int fileWatcherMonitoringDelayInMilliSeconds);
                ConversionSettings.FileWatcherMonitoringDelayInMilliSeconds = fileWatcherMonitoringDelayInMilliSeconds; // Delay between file directory fetch.

                int.TryParse(Environment.GetEnvironmentVariable("FILE_CONVERSION_OPENFILE_WAITTIME"), out int _envvaropenFileWaitTimeInSeconds);
                int.TryParse(configurationbuilder.GetSection("ConversionSettings:OpenFileWaitTimeInSeconds").Value, out int openFileWaitTimeInSeconds);
                ConversionSettings.OpenFileWaitTimeInSeconds = _envvaropenFileWaitTimeInSeconds == 0 ? openFileWaitTimeInSeconds : _envvaropenFileWaitTimeInSeconds; // Wait time for opening a file (specifically Excel)

                string syncfusionLicense =  Environment.GetEnvironmentVariable("FILE_CONVERSION_SYNCFUSIONKEY");
                //Fetching Syncfusion License from settings
                Syncfusion.Licensing.SyncfusionLicenseProvider.RegisterLicense(string.IsNullOrEmpty(syncfusionLicense) ? ConversionSettings.SyncfusionLicense: syncfusionLicense);

                // Comment in if running locally
                //string eventHubHost = configurationbuilder.GetSection("EventHub:Host").Value;
                //string eventHubPort = configurationbuilder.GetSection("EventHub:Port").Value;
                //string eventHubPassword = configurationbuilder.GetSection("EventHub:Password").Value;
                //string streamKey = configurationbuilder.GetSection("EventHub:StreamKey").Value;
                //string consumerGroup = "file-conversion-consumer-group";



                using var client = new HttpClient();
                HttpResponseMessage response = await client.GetAsync(Environment.GetEnvironmentVariable("RECORD_FORMATS"));
                response.EnsureSuccessStatusCode();
                string responseBody = await response.Content.ReadAsStringAsync();
                var formats = JsonSerializer.Deserialize<JsonNode>(responseBody);
                //var conversionformats = formats["conversion"];

                ConversionSettings.ConversionFormats = formats["conversion"].AsArray().Select(format => format.ToString()).ToArray();
                ConversionSettings.DedupeFormats = formats["dedupe"].AsArray().Select(format => format.ToString()).ToArray();
                ConversionSettings.IncompatibleFormats = formats["nonredactable"].AsArray().Select(format => format.ToString()).ToArray();

                string eventHubHost = Environment.GetEnvironmentVariable("REDIS_STREAM_HOST");
                string eventHubPort = Environment.GetEnvironmentVariable("REDIS_STREAM_PORT");
                string eventHubPassword = Environment.GetEnvironmentVariable("REDIS_STREAM_PASSWORD");
                string streamKey = Environment.GetEnvironmentVariable("REDIS_STREAM_KEY");
                string dedupeStreamKey = Environment.GetEnvironmentVariable("DEDUPE_STREAM_KEY");
                string consumerGroup = Environment.GetEnvironmentVariable("REDIS_STREAM_CONSUMER_GROUP");

                using ConnectionMultiplexer redis = ConnectionMultiplexer.Connect(
                 new ConfigurationOptions
                 {
                     EndPoints = { $"{eventHubHost}:{eventHubPort}" },
                     Password = eventHubPassword
                 });

                var db = redis.GetDatabase();

                string latest = "$";
                try
                {
                    db.StreamCreateConsumerGroup(streamKey, consumerGroup, "$");
                    Log.Information("Redis consumer group {ConsumerGroup} created on stream {StreamKey}",
                        consumerGroup.Trim(), streamKey);
                }
                catch (Exception ex)
                {
                    if (ex.Message != "BUSYGROUP Consumer Group name already exists")
                    {
                        Log.Error(ex, "Error creating Redis consumer group {ConsumerGroup} on stream {StreamKey} at {Host}:{Port}",
                            consumerGroup, streamKey, eventHubHost, eventHubPort);
                    }
                    else
                    {
                        Log.Information("Redis consumer group {ConsumerGroup} already exists on stream {StreamKey}",
                            consumerGroup.Trim(), streamKey);
                    }
                }

                while (true)
                {
                    var messages = db.StreamReadGroup(streamKey, consumerGroup, "c1");
                    if (messages.Length > 0)
                    {
                        foreach (StreamEntry message in messages)
                        {
                            using var _rn = LogContext.PushProperty("RequestNumber", (string)message["requestnumber"]);
                            using var _bc = LogContext.PushProperty("BCGovCode", (string)message["bcgovcode"]);
                            using var _mr = LogContext.PushProperty("MinistryRequestId", (string)message["ministryrequestid"]);
                            using var _ji = LogContext.PushProperty("JobId", (string)message["jobid"]);
                            using var _fn = LogContext.PushProperty("Filename", (string)message["filename"]);
                            using var _fp = LogContext.PushProperty("Filepath", (string)message["s3filepath"]);

                            using (DBHandler dbhandler = new DBHandler())
                            {
                                try
                                {
                                    // Console.WriteLine("Message ID: {0} Converting: {1}", message.Id, message["s3filepath"]);

                                    ValidateMessage(message);
                                    await dbhandler.recordJobStart(message);
                                    Log.Information("Job started");
                                    using (S3Handler s3handler = new S3Handler())
                                    {
                                        var filePath = (string)message["s3filepath"];
                                        string bucket = filePath.Split("/")[3];
                                        S3AccessKeys s3AccessKeys = await dbhandler.getAccessKeyFromDB(bucket);
                                        var sw = Stopwatch.StartNew();
                                        var (attachments, convertedSize) = await s3handler.ConvertFile(message, s3AccessKeys);
                                        sw.Stop();
                                        Log.Information("File conversion completed in {Duration}ms", sw.Elapsed.TotalMilliseconds);

                                        // Record any child tasks before sending them to Redis Streams
                                        Dictionary<string, Dictionary<string, string>> jobIDs = await dbhandler.recordJobEnd(message, false, "", attachments);
                                        if (attachments != null && attachments.Count > 0)
                                        {
                                            for (int i = 0; i < attachments.Count; i++)
                                            {
                                                Dictionary<string, object> attributesDictionary = JsonSerializer.Deserialize<Dictionary<string, object>>(attachments[i]["attributes"]);
                                                string _incompatible;
                                                if (attributesDictionary.ContainsKey("incompatible"))
                                                {
                                                    _incompatible = attributesDictionary["incompatible"].ToString().ToLower();
                                                } else {
                                                    _incompatible = "false";
                                                }
                                                if (Array.IndexOf(ConversionSettings.ConversionFormats, attachments[i]["extension"].ToLower()) == -1)
                                                {
                                                    db.StreamAdd(dedupeStreamKey, new NameValueEntry[]
                                                    {
                                                        new("s3filepath", attachments[i]["filepath"]),
                                                        new("requestnumber", message["requestnumber"]),
                                                        new("bcgovcode", message["bcgovcode"]),
                                                        new("filename", attachments[i]["filename"]),
                                                        new("ministryrequestid", message["ministryrequestid"]),
                                                        new("attributes", attachments[i]["attributes"]),
                                                        new("batch", message["batch"]),
                                                        new("jobid", jobIDs[attachments[i]["filepath"]]["jobID"]),
                                                        new("documentmasterid", jobIDs[attachments[i]["filepath"]]["masterID"]),
                                                        new("incompatible", _incompatible),
                                                        new("trigger", "attachment"),
                                                        new("createdby", message["createdby"]),
                                                        new("usertoken", message["usertoken"])
                                                    });
                                                    Log.Information("Queued attachment to DEDUPE STREAM {TargetStream}: {AttachmentFilename} ({AttachmentExtension})", dedupeStreamKey,
                                                        attachments[i]["filename"], attachments[i]["extension"]);
                                                }
                                                else
                                                {
                                                    db.StreamAdd(streamKey, new NameValueEntry[]
                                                    {
                                                        new("s3filepath", attachments[i]["filepath"]),
                                                        new("requestnumber", message["requestnumber"]),
                                                        new("bcgovcode", message["bcgovcode"]),
                                                        new("filename", attachments[i]["filename"]),
                                                        new("ministryrequestid", message["ministryrequestid"]),
                                                        new("attributes", attachments[i]["attributes"]),
                                                        new("batch", message["batch"]),
                                                        new("parentfilepath", message["s3filepath"]),
                                                        new("parentfilename", message["filename"]),
                                                        new("jobid", jobIDs[attachments[i]["filepath"]]["jobID"]),
                                                        new("documentmasterid", jobIDs[attachments[i]["filepath"]]["masterID"]),
                                                        new("trigger", "attachment"),
                                                        new("createdby", message["createdby"]),
                                                        new("usertoken", message["usertoken"])
                                                    });
                                                    Log.Information("Queued attachment to CONVERSION STREAM {TargetStream}: {AttachmentFilename} ({AttachmentExtension})",
                                                        streamKey, attachments[i]["filename"], attachments[i]["extension"]);
                                                }
                                            }
                                        }
                                        string newFilename = Path.ChangeExtension(message["s3filepath"], ".pdf");
                                        var attributes = JsonSerializer.Deserialize<JsonNode>(message["attributes"]);
                                        attributes["convertedfilesize"] = JsonValue.Create(convertedSize);
                                        db.StreamAdd(dedupeStreamKey, new NameValueEntry[]
                                        {
                                            new("s3filepath", Path.ChangeExtension(message["s3filepath"], ".pdf")),
                                            new("requestnumber", message["requestnumber"]),
                                            new("bcgovcode", message["bcgovcode"]),
                                            new("filename", message["filename"]),
                                            new("ministryrequestid", message["ministryrequestid"]),
                                            new("attributes", attributes.ToJsonString()),
                                            new("batch", message["batch"]),
                                            new("jobid", jobIDs[newFilename]["jobID"]),
                                            new("documentmasterid", message["documentmasterid"]),
                                            new("outputdocumentmasterid", jobIDs[newFilename]["masterID"]),
                                            new("trigger", message["trigger"]),
                                            new("createdby", message["createdby"]),
                                            new("usertoken", message["usertoken"])
                                        });
                                        Log.Information("Queued converted file to DEDUPE STREAM {TargetStream}", dedupeStreamKey);
                                        latest = message.Id;
                                        db.StringSet($"{latest}:lastid", latest);
                                        db.StreamAcknowledge(streamKey, consumerGroup, message.Id);
                                        Log.Information("Job completed successfully");
                                    }
                                }
                                catch (MissingFieldException ex)
                                {
                                    Log.Warning(ex, "Job skipped — missing required field");
                                }
                                catch (Exception ex)
                                {
                                    var errorMessage = $" Error happened while converting {message["s3filepath"]}. Exception message : {ex.Message}, StackTrace :{ex.StackTrace}";
                                    Log.Error(ex, "Error converting file");
                                    await dbhandler.recordJobEnd(message, true, errorMessage, new List<Dictionary<string, String>>());
                                }

                            }
                        }
                    }
                    else
                    {

                        // Console.WriteLine("No new messages after {0}", latest);
                    }
                    
                }
            }
            catch (Exception ex)
            {
                Log.Fatal(ex, "Unhandled error in FOI File Conversion service");
            }
            finally
            {
                Log.CloseAndFlush();
            }
        }


        private static void ValidateMessage(StreamEntry message)
        {
            if (message["s3filepath"].IsNull) { throw new MissingFieldException($"Redis stream message missing field 's3filepath'"); }
            if (message["requestnumber"].IsNull) { throw new MissingFieldException($"Redis stream message missing field 'requestnumber'"); }
            if (message["bcgovcode"].IsNull) { throw new MissingFieldException($"Redis stream message missing field 'bcgovcode'"); }
            if (message["filename"].IsNull) { throw new MissingFieldException($"Redis stream message missing field 'filename'"); }
            if (message["ministryrequestid"].IsNull) { throw new MissingFieldException($"Redis stream message missing field 'ministryrequestid'"); }
            if (message["attributes"].IsNull) { throw new MissingFieldException($"Redis stream message missing field 'attributes'"); }
            if (message["batch"].IsNull) { throw new MissingFieldException($"Redis stream message missing field 'batch'"); }
            if (message["jobid"].IsNull) { throw new MissingFieldException($"Redis stream message missing field 'jobid'"); }
            if (message["documentmasterid"].IsNull) { throw new MissingFieldException($"Redis stream message missing field 'documentmasterid'"); }
            if (message["trigger"].IsNull) { throw new MissingFieldException($"Redis stream message missing field 'trigger'"); }
            if (message["createdby"].IsNull) { throw new MissingFieldException($"Redis stream message missing field 'createdby'"); }
            if (message["usertoken"].IsNull) { throw new MissingFieldException($"Redis stream message missing field 'usertoken'"); }
        }
    }
}

