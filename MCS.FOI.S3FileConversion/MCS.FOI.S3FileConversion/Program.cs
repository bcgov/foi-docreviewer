using System;
using System.IO;
using Microsoft.Extensions.Configuration;
//using Serilog;
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

namespace MCS.FOI.S3FileConversion
{
    class Program
    {
        static async System.Threading.Tasks.Task Main(string[] args)
        {
            //string s3FilePath = args[0];
            Console.WriteLine("Hello World");

            var configurationbuilder = new ConfigurationBuilder()
                        .AddJsonFile($"appsettings.json", true, true)
                        //.AddJsonFile($"appsettings.{environmentName}.json", true, true) // TEMP: Commented out, will track back when we migrate to Cloud/OS in future
                        .AddEnvironmentVariables().Build();



            //Log.Logger = new LoggerConfiguration()
            //.ReadFrom.Configuration(configurationbuilder)
            //.CreateLogger();


            //string S3Host = configurationbuilder.GetSection("ConversionSettings:S3Host").Value;

            


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



        
    }
}
