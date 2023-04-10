using MCS.FOI.S3FileConversion.Utilities;
using Microsoft.Extensions.Configuration;
using Serilog;
using StackExchange.Redis;

namespace MCS.FOI.S3FileConversion
{
    class Program
    {
        static async System.Threading.Tasks.Task Main(string[] args)
        {

            try
            {
                Log.Information("MCS FOI S3FileConversion Service is up");
                Console.WriteLine("MCS FOI S3FileConversion Service is up");
                var configurationbuilder = new ConfigurationBuilder()
                        .AddJsonFile($"appsettings.json", true, true)
                        .AddEnvironmentVariables().Build();


                //Fetching Configuration values from setting file { appsetting.{ environment_platform}.json}
                ConversionSettings.SyncfusionLicense = configurationbuilder.GetSection("ConversionSettings:SyncfusionLicense").Value;
               
                IConfigurationSection ministryConfigSection = configurationbuilder.GetSection("ConversionSettings:MinistryIncomingPaths");

                int.TryParse(configurationbuilder.GetSection("ConversionSettings:FailureAttemptCount").Value, out int failureattempt);
                ConversionSettings.FailureAttemptCount = failureattempt;// Max. recovery attempts after a failure.

                int.TryParse(configurationbuilder.GetSection("ConversionSettings:WaitTimeInMilliSeconds").Value, out int waittimemilliseconds);
                ConversionSettings.WaitTimeInMilliSeconds = waittimemilliseconds; // Wait time between recovery attempts after a failure

                int.TryParse(configurationbuilder.GetSection("ConversionSettings:FileWatcherMonitoringDelayInMilliSeconds").Value, out int fileWatcherMonitoringDelayInMilliSeconds);
                ConversionSettings.FileWatcherMonitoringDelayInMilliSeconds = fileWatcherMonitoringDelayInMilliSeconds; // Delay between file directory fetch.

                //Fetching Syncfusion License from settings
                Syncfusion.Licensing.SyncfusionLicenseProvider.RegisterLicense(ConversionSettings.SyncfusionLicense);

                // Comment in if running locally
                //string eventHubHost = configurationbuilder.GetSection("EventHub:Host").Value;
                //string eventHubPort = configurationbuilder.GetSection("EventHub:Port").Value;
                //string eventHubPassword = configurationbuilder.GetSection("EventHub:Password").Value;
                //string streamKey = configurationbuilder.GetSection("EventHub:StreamKey").Value;
                //string consumerGroup = "file-conversion-consumer-group";

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

               var  db = redis.GetDatabase();                           

                string latest = "$";
                try
                {
                    db.StreamCreateConsumerGroup(streamKey, consumerGroup, "$");
                }
                catch (Exception ex)
                {
                    if (ex.Message != "BUSYGROUP Consumer Group name already exists")
                    {
                        Console.WriteLine($"Error happened while accessing REDIS Stream : {streamKey} | Consumergrourp : {consumerGroup} | Host : {eventHubHost} | | HostPort : {eventHubPort}");
                    }
                }

                while (true)
                {
                    var messages = db.StreamReadGroup(streamKey, consumerGroup, "c1");
                    if (messages.Length > 0)
                    {
                        foreach (StreamEntry message in messages)
                        {                            
                            try
                            {
                                //Console.WriteLine("Message ID: {0} Converting: {1}", message.Id, message["s3filepath"]);
                                ValidateMessage(message);
                                await DBHandler.recordJobStart(message);
                                List<Dictionary<string, String>> attachments = await S3Handler.ConvertFile(message);
                                // Record any child tasks before sending them to Redis Streams
                                Dictionary<string, Dictionary<string, string>> jobIDs = await DBHandler.recordJobEnd(message, false, "", attachments);
                                if (attachments != null && attachments.Count > 0)
                                {
                                    for (int i = 0; i < attachments.Count; i++)
                                    {
                                        string[] conversionFormats = { ".doc", ".docx", ".xls", ".xlsx", ".ics", ".msg" };
                                        if (Array.IndexOf(conversionFormats, attachments[i]["extension"]) == -1)
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
                                                new("trigger", "attachment"),
                                                new("createdby",  message["createdby"])
                                            });
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
                                                new("createdby",  message["createdby"])
                                            });
                                        }
                                    }
                                }
                                string newFilename = Path.ChangeExtension(message["s3filepath"], ".pdf");
                                db.StreamAdd(dedupeStreamKey, new NameValueEntry[]
                                {
                                new("s3filepath", Path.ChangeExtension(message["s3filepath"], ".pdf")),
                                new("requestnumber", message["requestnumber"]),
                                new("bcgovcode", message["bcgovcode"]),
                                new("filename", message["filename"]),
                                new("ministryrequestid", message["ministryrequestid"]),
                                new("attributes", message["attributes"].ToString()),
                                new("batch", message["batch"]),
                                new("jobid", jobIDs[newFilename]["jobID"]),
                                new("documentmasterid", message["documentmasterid"]),
                                new("outputdocumentmasterid", jobIDs[newFilename]["masterID"]),
                                new("trigger", message["trigger"]),
                                new("createdby",  message["createdby"])
                                });
                                latest = message.Id;
                                db.StringSet($"{latest}:lastid", latest);
                                db.StreamAcknowledge(streamKey, consumerGroup, message.Id);
                                
                            }
                            catch (MissingFieldException ex)
                            {                                
                                Console.WriteLine(ex.Message);
                            }
                            catch (Exception ex)
                            {
                                var errorMessage = $" Error happpened while converting {message["s3filepath"]}. Exception message : {ex.Message} , StackTrace :{ex.StackTrace}";
                                Console.WriteLine(errorMessage);
                                await DBHandler.recordJobEnd(message, true, errorMessage, new List<Dictionary<string, String>>());
                            }
                        }
                    }
                    else
                    {
                        //Console.WriteLine("No new messages after {0}", latest);
                    }
                    Thread.Sleep(6000);
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($" Error happpened while running the FOI File Conversion service. Exception message : {ex.Message} , StackTrace :{ex.StackTrace}");
                Log.Information($" Error happpened while running the FOI File Conversion service. Exception message : {ex.Message} , StackTrace :{ex.StackTrace}");
            }
            finally
            {
                Console.WriteLine("Press enter to exit.");
                Console.ReadLine();
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
        }
    }
}
