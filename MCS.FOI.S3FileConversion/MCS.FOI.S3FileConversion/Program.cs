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
        static async Task Main(string[] args)
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


                _ = int.TryParse(configurationbuilder.GetSection("ConversionSettings:FailureAttemptCount").Value, out int failureattempt);
                ConversionSettings.FailureAttemptCount = failureattempt;// Max. recovery attempts after a failure.

                _ = int.TryParse(configurationbuilder.GetSection("ConversionSettings:WaitTimeInMilliSeconds").Value, out int waittimemilliseconds);
                ConversionSettings.WaitTimeInMilliSeconds = waittimemilliseconds; // Wait time between recovery attempts after a failure
                                             
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

                string latest = "$";
                string streamKey = configurationbuilder.GetSection("EventHub:StreamKey").Value;

                while (true)
                {
                    var messages = db.StreamReadGroup(streamKey, "file-conversion-consumer-group", "c1");
                    if (messages.Length > 0) {
                        foreach (StreamEntry message in messages)
                        {
                            Console.WriteLine("Message ID: {0} Converting: {1}", message.Id, message["S3Path"]);
                            latest = message.Id;
                            db.StringSet($"{latest}:lastid", latest);
                            db.StreamAcknowledge(streamKey, "file-conversion-consumer-group", message.Id);
                            List<string> s3AttachmentPaths = await S3Handler.ConvertFile(message["S3Path"]);
                            if (s3AttachmentPaths != null && s3AttachmentPaths.Count > 0)
                            {
                                for (int i = 0; i < s3AttachmentPaths.Count; i++)
                                {
                                    db.StreamAdd(streamKey, new NameValueEntry[]
                                    { new("S3Path", s3AttachmentPaths[i]), new NameValueEntry("RequestNumber", latest)});
                                    db.StreamAcknowledge(streamKey, "file-conversion-consumer-group", message.Id);
                                }
                            }
                            Console.WriteLine("Finished Converting: {0}", message["S3Path"]);
                        }
                    }
                    else {
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
