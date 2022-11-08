using System;
using System.IO;
using Microsoft.Extensions.Configuration;
//using Serilog;
using Amazon.S3;
using Amazon.S3.Model;
using Amazon.Runtime;
using System.Linq;
using System.Net.Http;
using Amazon;
using System.Collections.Generic;
using System.Net.Http;
using System.Net.Http.Headers;
using MCS.FOI.ExcelToPDF;

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


            string S3AccessKeyID = configurationbuilder.GetSection("ConversionSettings:S3AccessKeyID").Value;
            string S3AccessSecretKey = configurationbuilder.GetSection("ConversionSettings:S3AccessSecretKey").Value;
            string S3Bucket = configurationbuilder.GetSection("ConversionSettings:S3Bucket").Value;
            string S3ServiceAccount = configurationbuilder.GetSection("ConversionSettings:S3ServiceAccount").Value;
            string S3Host = configurationbuilder.GetSection("ConversionSettings:S3Host").Value;

            IAmazonS3 s3;


            AWSCredentials AWSCredentials = new BasicAWSCredentials("access key", "secret access key");
            AmazonS3Config config = new AmazonS3Config
            {
                //USEast1RegionalEndpointValue = Amazon.Runtime.S3UsEast1RegionalEndpointValue.Regional,

                ServiceURL = "https://citz-foi-prod.objectstore.gov.bc.ca"
                //RegionEndpoint = RegionEndpoint.USEast1,
                //ServiceURL = S3Host,
            };
            //config.SignatureVersion = "false";
            //config.SignatureVersion = "AWS4-HMAC-SHA256";

            AmazonS3Client s3Client = new AmazonS3Client(AWSCredentials, config);

            using (s3 = new AmazonS3Client(AWSCredentials, config))
            {
                //var list = await s3.ListBucketsAsync();
                //var buckets = list.Buckets.Select(x => x.BucketName);

                //Console.WriteLine(buckets.Count());

                ListBucketsResponse listresponse = await s3Client.ListBucketsAsync();
                foreach (S3Bucket b in listresponse.Buckets)
                {
                    Console.WriteLine("{0}\t{1}", b.BucketName, b.CreationDate);
                }

                var presignedGetURL = GetPresignedURL(s3, "edu-dev/test1.xlsx", HttpVerb.GET);
                Console.WriteLine(presignedGetURL);

                var client = new HttpClient();
                HttpResponseMessage response = await client.GetAsync(presignedGetURL); 
                response.EnsureSuccessStatusCode();
                //string responseBody = await response.Content.ReadAsStringAsync();
                Stream responseStream = response.Content.ReadAsStream();
                ExcelFileProcessor excelFileProcessor = new ExcelFileProcessor(responseStream, "C:\\Users\\Nicholas Kan\\Documents\\Test Attachments\\uploaded\\test1.xlsx");
                excelFileProcessor.IsSinglePDFOutput = false;
                excelFileProcessor.WaitTimeinMilliSeconds = 5000;
                excelFileProcessor.FailureAttemptCount = 10;
                var (converted, message, PdfOutputFilePath, output) = excelFileProcessor.ConvertToPDF();

                var presignedPutURL = GetPresignedURL(s3, "edu-dev/test1.pdf", HttpVerb.PUT);

                output.Position = 0;
                StreamContent strm = new StreamContent(output);
                //StreamContent strm = new StreamContent(new FileStream("C:\\Users\\Nicholas Kan\\Documents\\Test Attachments\\uploaded\\test1.xlsx\\_Sheet1.pdf", FileMode.Open, FileAccess.Read));
                strm.Headers.ContentType = new System.Net.Http.Headers.MediaTypeHeaderValue("application/octet-stream");
                HttpResponseMessage putRespMsg = await client.PutAsync(presignedPutURL, strm);

                //Console.WriteLine(responseBody);

                //listobjectsv2request request = new listobjectsv2request();
                //request.bucketname = "/edu-dev";
                //listobjectsv2response response = await s3client.listobjectsv2async(request);
                //foreach (s3object o in response.s3objects)
                //{
                //    console.writeline("{0}\t{1}\t{2}", o.key, o.size, o.lastmodified);
                //}

                //var listReq = new ListObjectsRequest
                //{
                //    BucketName = "/dev-forms-foirequests"
                //};

                //var listResponse = await s3Client.ListObjectsAsync(listReq);

                //foreach (S3Object entry in listResponse.S3Objects)
                //{
                //    Console.Write(entry.Key);
                //}

                //var filePath = S3Host + "/dev-forms-foirequests/test1.xlsx";

                //GetObjectRequest request = new GetObjectRequest
                //{
                //    BucketName = "edu-dev",
                //    Key = "edu-dev/test1.xlsx"
                //};
                //request.ResponseHeaderOverrides.CacheControl = "no-cache, max-age=0";

                ////try
                ////{
                //using GetObjectResponse response = await s3.GetObjectAsync(request);
                //await response.WriteResponseStreamToFileAsync("C:\\Users\\Nicholas Kan\\Documents\\Test Attachments\\uploaded\\test1.xlsx", true, System.Threading.CancellationToken.None);
            }
            //}
            //catch (AmazonS3Exception ex)
            //{
            //    Console.WriteLine($"Error encountered on server. Message:'{ex.Message}' getting list of objects.");
            //}

        }
        private static string GetPresignedURL(IAmazonS3 s3, string fileName, HttpVerb method)
        {
            AWSConfigsS3.UseSignatureVersion4 = true;
            GetPreSignedUrlRequest request1 = new()
            {
                Key = fileName,
                Verb = method,
                //ContentType = "application/pdf",
                Expires = DateTime.Now.AddHours(1),
                Protocol = Protocol.HTTPS,
                //ServerSideEncryptionKeyManagementServiceKeyId = S3AccessSecretKey,
                //ServerSideEncryptionMethod = ServerSideEncryptionMethod.AES256
            };
            //request1.ResponseHeaderOverrides.ContentType = "application/df";
            return s3.GetPreSignedURL(request1);
        }
    }
}
