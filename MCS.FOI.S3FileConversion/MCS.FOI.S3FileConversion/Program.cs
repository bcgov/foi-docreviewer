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
                ConversionSettings.HTMLtoPdfWebkitPath = configurationbuilder.GetSection("ConversionSettings:HTMLtoPdfWebkitPath").Value;
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

                //CreateHostBuilder(args).Build().Run();

                string eventHubHost = configurationbuilder.GetSection("EventHub:Host").Value;
                string eventHubPort = configurationbuilder.GetSection("EventHub:Port").Value;
                //string eventHubPort = configurationbuilder.GetSection("EventHub:Port").Value;
                ConnectionMultiplexer redis = ConnectionMultiplexer.Connect(
                new ConfigurationOptions
                {
                    EndPoints = { $"{eventHubHost}:{eventHubPort}" },
                    Password = configurationbuilder.GetSection("EventHub:Password").Value
                });

                var db = redis.GetDatabase();
                var pong = await db.PingAsync();
                Console.WriteLine(pong);

                //string latest = "1667951169543-0";
                string latest = "$";
                string streamKey = configurationbuilder.GetSection("EventHub:StreamKey").Value;
                //db.StreamCreateConsumerGroup(streamKey, "file-conversion-consumer-group", "$");

                while (true)
                {
                    var messages = db.StreamReadGroup(streamKey, "file-conversion-consumer-group", "c1");
                    if (messages.Length > 0) {
                        foreach (StreamEntry message in messages)
                        {
                            //Console.WriteLine(message);
                            Console.WriteLine("Message ID: {0} Converting: {1}", message.Id, message["S3Path"]);
                            List<String> s3AttachmentPaths= await S3Handler.convertFile(message["S3Path"]);
                            latest = message.Id;
                            db.StringSet($"{latest}:lastid", latest);
                            for(int i = 0; i < s3AttachmentPaths.Count; i++)
                            {
                                db.StreamAdd(streamKey, new NameValueEntry[]
                                { new("S3Path", s3AttachmentPaths[i]), new NameValueEntry("RequestNumber", latest)});
                            }

                            db.StreamAcknowledge(streamKey, "file-conversion-consumer-group", message.Id);
                            Console.WriteLine("Finished Converting: {0}", message["S3Path"]); 
                        }
                    } else {
                        Console.WriteLine("No new messages after {0}", latest);
                    }
                    Thread.Sleep(6000);
                }

            }
            catch (Exception ex)
            {
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


    }
}
