using System;
using System.IO;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using MCS.FOI.S3FileConversion.Utilities;
using Serilog;
using System.Linq;
using System.Net.Http;
using Amazon;
using System.Collections.Generic;
using System.Net.Http;
using System.Net.Http.Headers;
using StackExchange.Redis;
using System;
using System.Threading.Tasks;
using SkiaSharp;
using ILogger = Serilog.ILogger;
using System.Text.Json;
using System.Reflection.Metadata;
using System.Text.Json.Nodes;
using System.Xml.Linq;

namespace MCS.FOI.S3FileConversion
{
    class Program
    {
        static async System.Threading.Tasks.Task Main(string[] args)
        {

            try
            {
                Log.Information("MCS FOI S3FileConversion Service is up");
                Console.WriteLine("Hello World");
                var configurationbuilder = new ConfigurationBuilder()
                        .AddJsonFile($"appsettings.json", true, true)
                        .AddEnvironmentVariables().Build();

                //Log.Logger = new LoggerConfiguration().ReadFrom.Configuration(configurationbuilder).CreateLogger();

                //string S3Host = configurationbuilder.GetSection("ConversionSettings:S3Host").Value;


                //Fetching Configuration values from setting file { appsetting.{ environment_platform}.json}
                //ConversionSettings.DeploymentPlatform = environmentName.ToLower().StartsWith("linux") ? Platform.Linux : Platform.Windows; //KEEPING MULTI PLATFORM CODE BASE LOGIC FOR FUTURE REFERENCE
                ConversionSettings.DeploymentPlatform = Platform.Windows; //Fixing to Windows platform for Win Server VM deployment, once with Linux/OS , will take environment
                ConversionSettings.FileWatcherStartDate = configurationbuilder.GetSection("ConversionSettings:FileWatcherStartDate").Value;
                ConversionSettings.SyncfusionLicense = configurationbuilder.GetSection("ConversionSettings:SyncfusionLicense").Value;
                ConversionSettings.CFRArchiveFoldertoSkip = configurationbuilder.GetSection("ConversionSettings:CFRArchiveFoldertoSkip").Value;
                IConfigurationSection ministryConfigSection = configurationbuilder.GetSection("ConversionSettings:MinistryIncomingPaths");

                int.TryParse(configurationbuilder.GetSection("ConversionSettings:FailureAttemptCount").Value, out int failureattempt);
                ConversionSettings.FailureAttemptCount = failureattempt;// Max. recovery attempts after a failure.

                int.TryParse(configurationbuilder.GetSection("ConversionSettings:WaitTimeInMilliSeconds").Value, out int waittimemilliseconds);
                ConversionSettings.WaitTimeInMilliSeconds = waittimemilliseconds; // Wait time between recovery attempts after a failure

                int.TryParse(configurationbuilder.GetSection("ConversionSettings:FileWatcherMonitoringDelayInMilliSeconds").Value, out int fileWatcherMonitoringDelayInMilliSeconds);
                ConversionSettings.FileWatcherMonitoringDelayInMilliSeconds = fileWatcherMonitoringDelayInMilliSeconds; // Delay between file directory fetch.

                int.TryParse(configurationbuilder.GetSection("ConversionSettings:DayCountBehindToStart").Value, out int count);
                ConversionSettings.DayCountBehindToStart = count; // days behind to start from for File watching, this is for DirectoryList Object to set up static algo for FileWacthing, till DB integration.

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

                ConnectionMultiplexer redis = ConnectionMultiplexer.Connect(
                new ConfigurationOptions
                {
                    EndPoints = { $"{eventHubHost}:{eventHubPort}" },
                    Password = eventHubPassword
                });

                var db = redis.GetDatabase();
                var pong = await db.PingAsync();
                Console.WriteLine(pong);

                string latest = "$";
                try
                {
                    db.StreamCreateConsumerGroup(streamKey, consumerGroup, "$");
                }
                catch (Exception ex)
                {
                    if (ex.Message != "BUSYGROUP Consumer Group name already exists")
                    {
                        throw ex;
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
                                Console.WriteLine("Message ID: {0} Converting: {1}", message.Id, message["s3filepath"]);
                                Console.WriteLine("Attributes: {0}", message["attributes"]);
                                Console.WriteLine("Parentfilename: {0}", message["parentfilename"]);
                                ValidateMessage(message);
                                await DBHandler.recordJobStart(message);
                                List<Dictionary<string, String>> attachments = await S3Handler.ConvertFile(message["s3filepath"]);
                                // Record any child tasks before sending them to Redis Streams
                                Dictionary<string, string> jobIDs = await DBHandler.recordJobEnd(message, false, "", attachments);
                                if (attachments != null && attachments.Count > 0)
                                {
                                    for (int i = 0; i < attachments.Count; i++)
                                    {
                                        var attributes = JsonSerializer.Deserialize<JsonNode>(message["attributes"]);
                                        attributes["filesize"] = JsonValue.Create(attachments[i]["size"]);
                                        attributes["isattachment"] = JsonValue.Create(true);
                                        if (attachments[i].ContainsKey("lastmodified"))
                                        {
                                            attributes["lastmodified"] = JsonValue.Create(attachments[i]["lastmodified"]);
                                        }
                                        if (attachments[i]["filename"].ToLower().Contains(".pdf")) 
                                        {
                                            db.StreamAdd(dedupeStreamKey, new NameValueEntry[]
                                            {
                                                new("s3filepath", attachments[i]["filepath"]),
                                                new("requestnumber", message["requestnumber"]),
                                                new("bcgovcode", message["bcgovcode"]),
                                                new("filename", attachments[i]["filename"]),
                                                new("ministryrequestid", message["ministryrequestid"]),
                                                new("attributes", attributes.ToJsonString()),
                                                new("batch", message["batch"]),
                                                new("jobid", jobIDs[attachments[i]["filepath"]]),
                                                new("trigger", "fileconversion"),
                                            });
                                        } 
                                        else
                                        {
                                            db.StreamAdd(streamKey, new NameValueEntry[]
                                            //{ new("s3filepath", attachments[i].Key), new NameValueEntry("RequestNumber", latest)});
                                            {
                                                new("s3filepath", attachments[i]["filepath"]),
                                                new("requestnumber", message["requestnumber"]),
                                                new("bcgovcode", message["bcgovcode"]),
                                                new("filename", attachments[i]["filename"]),
                                                new("ministryrequestid", message["ministryrequestid"]),
                                                new("attributes", attributes.ToJsonString()),
                                                new("batch", message["batch"]),
                                                new("parentfilepath", message["s3filepath"]),
                                                new("parentfilename", message["filename"]),
                                                new("jobid", jobIDs[attachments[i]["filepath"]]),
                                                new("trigger", "attachment"),
                                            });

                                        }
                                    }
                                }
                                db.StreamAdd(dedupeStreamKey, new NameValueEntry[]
                                {
                                new("s3filepath", Path.ChangeExtension(message["s3filepath"], ".pdf")),
                                new("requestnumber", message["requestnumber"]),
                                new("bcgovcode", message["bcgovcode"]),
                                new("filename", message["filename"]),
                                new("ministryrequestid", message["ministryrequestid"]),
                                new("attributes", message["attributes"].ToString()),
                                new("batch", message["batch"]),
                                new("jobid", jobIDs[Path.ChangeExtension(message["s3filepath"], ".pdf")]),
                                new("trigger", "fileconversion"),
                                });
                                latest = message.Id;
                                db.StringSet($"{latest}:lastid", latest);
                                db.StreamAcknowledge(streamKey, consumerGroup, message.Id);
                                Console.WriteLine("Finished Converting: {0}", message["s3filepath"]);
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
                        Console.WriteLine("No new messages after {0}", latest);
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

        //public static IHostBuilder CreateHostBuilder(string[] args) =>
        //   Host.CreateDefaultBuilder(args)

        //       .ConfigureServices((hostContext, services) =>
        //       {
        //           services.AddHostedService<Worker>(); // Dependency Injection of  Worker / BG Service               
        //       })
        //   .UseWindowsService(); // Marking as Windows Service to silently execute the process.

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
            if (message["trigger"].IsNull) { throw new MissingFieldException($"Redis stream message missing field 'trigger'"); }

        }
    }
}
