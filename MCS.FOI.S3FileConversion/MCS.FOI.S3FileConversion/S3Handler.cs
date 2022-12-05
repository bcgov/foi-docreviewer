using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using Amazon.S3;
using Amazon.S3.Model;
using Amazon.Runtime;
using Microsoft.Extensions.Configuration;
using Amazon;
using MCS.FOI.S3FileConversion.Utilities;
using MCS.FOI.ExcelToPDF;
using MCS.FOI.CalendarToPDF;
using MCS.FOI.DocToPDF;
using MCS.FOI.EMLToPDF;
using MCS.FOI.MSGToPDF;
using Npgsql;
using Serilog;


namespace MCS.FOI.S3FileConversion
{
    internal class S3AccessKeys
    {
        public string s3accesskey { get; set; }
        public string s3secretkey { get; set; }
    }
    internal class S3Handler
    {
        public static async System.Threading.Tasks.Task<List<String>> ConvertFile(string filePath)
        {
            // Get S3 Access credentials based on ministry
            var cb = new ConfigurationBuilder().AddJsonFile($"s3access.json", true, true).AddEnvironmentVariables().Build();
            string bucket = filePath.Split("/")[3];
            // Comment in if running locally
            //string S3Host = cb.GetSection("S3Host").Value;
            //string S3AccessKeyID = cb.GetSection($"AccountMapping:{bucket}:S3AccessKeyID").Value;
            //string S3AccessSecretKey = cb.GetSection($"AccountMapping:{bucket}:S3AccessSecretKey").Value;
            //string S3ServiceAccount = cb.GetSection($"AccountMapping:{bucket}:S3ServiceAccount").Value;
            S3AccessKeys s3AccessKeys = await getAccessKeyFromDB(bucket);
            string S3AccessKeyID = s3AccessKeys.s3accesskey;
            string S3AccessSecretKey = s3AccessKeys.s3secretkey;
            string S3Host = Environment.GetEnvironmentVariable("S3_HOST");

            List<string> attachmentKeys = new List<string>();
            try
            {
                // Initialize S3 Client
                IAmazonS3 s3;
                AWSCredentials AWSCredentials = new BasicAWSCredentials(S3AccessKeyID, S3AccessSecretKey);
                AmazonS3Config config = new()
                {
                    ServiceURL = S3Host
                };

                AmazonS3Client s3Client = new(AWSCredentials, config);

                using (s3 = new AmazonS3Client(AWSCredentials, config))
                {
                    // Get File from s3
                    var fileKey = filePath.Split(S3Host + '/')[1];
                    var presignedGetURL = GetPresignedURL(s3, fileKey, HttpVerb.GET);

                    var client = new HttpClient();
                    HttpResponseMessage response = await client.GetAsync(presignedGetURL);
                    response.EnsureSuccessStatusCode();
                    Stream responseStream = response.Content.ReadAsStream();

                    // Convert File
                    string extension = Path.GetExtension(fileKey);
                    Stream output = new MemoryStream();
                    Dictionary<MemoryStream, string> attachments = new();

                    switch (extension)
                    {
                        case ".xls":
                        case ".xlsx":
                            output = ConvertExcelFiles(responseStream);
                            break;
                        case ".ics":
                            (output, attachments) = ConvertCalendarFiles(responseStream);
                            break;
                        case ".msg":
                            (output, attachments) = ConvertMSGFiles(responseStream);
                            break;
                        //case ".eml":
                        //    output = convertEMLFiles(responseStream);
                        //    break;
                        case ".doc":
                        case ".docx":
                            output = ConvertDocFiles(responseStream);
                            break;
                    }


                    // Save converted pdf back to s3
                    var newKey = Path.ChangeExtension(fileKey, ".pdf");
                    var presignedPutURL = GetPresignedURL(s3, newKey, HttpVerb.PUT);
                    string folder = filePath.Split("/")[4];

                    output.Position = 0;
                    StreamContent strm = new(output);
                    strm.Headers.ContentType = new System.Net.Http.Headers.MediaTypeHeaderValue("application/octet-stream");
                    HttpResponseMessage putRespMsg = await client.PutAsync(presignedPutURL, strm);
                    
                    if (attachments != null && attachments.Count > 0)
                    {
                        foreach (KeyValuePair<MemoryStream, string> attachment in attachments)
                        {
                            attachment.Key.Position=0;
                            var newAttachmentKey = bucket+"/"+folder+"/"+ attachment.Value;
                            var attachmentPresignedPutURL = GetPresignedURL(s3, newAttachmentKey, HttpVerb.PUT);
                            attachmentKeys.Add(S3Host+"/"+newAttachmentKey);
                            StreamContent attachmentstrm = new StreamContent(attachment.Key);
                            strm.Headers.ContentType = new System.Net.Http.Headers.MediaTypeHeaderValue("application/octet-stream");
                            HttpResponseMessage putRespMsgAttachments = await client.PutAsync(attachmentPresignedPutURL, attachmentstrm);
                        }
                    }

                }

            }
            catch (AmazonS3Exception ex)
            {
                Console.WriteLine($"Error encountered on server. Message:'{ex.Message}' getting list of objects.");
            }
            return attachmentKeys;
        }

        public static string GetPresignedURL(IAmazonS3 s3, string fileName, HttpVerb method)
        {
            AWSConfigsS3.UseSignatureVersion4 = true;
            GetPreSignedUrlRequest request = new()
            {
                Key = fileName,
                Verb = method,
                Expires = DateTime.Now.AddHours(1),
                Protocol = Protocol.HTTPS,
            };
            return s3.GetPreSignedURL(request);
        }

        private static Stream ConvertExcelFiles(Stream input)
        {
            ExcelFileProcessor excelFileProcessor = new ExcelFileProcessor(input)
            {
                IsSinglePDFOutput = false,
                WaitTimeinMilliSeconds = ConversionSettings.WaitTimeInMilliSeconds,
                FailureAttemptCount = ConversionSettings.FailureAttemptCount
            };
            var (converted, message, output) = excelFileProcessor.ConvertToPDF();
            return output;
        }

        private static (Stream, Dictionary<MemoryStream, string>) ConvertCalendarFiles(Stream input)
        {
            CalendarFileProcessor calendarFileProcessor = new CalendarFileProcessor(input)
            {
                WaitTimeinMilliSeconds = ConversionSettings.WaitTimeInMilliSeconds,
                FailureAttemptCount = ConversionSettings.FailureAttemptCount
            };
            var (isProcessed, Message, output, attachments) = calendarFileProcessor.ProcessCalendarFiles();
            return (output, attachments);
        }

        private static (Stream, Dictionary<MemoryStream, string>) ConvertMSGFiles(Stream input)
        {
            MSGFileProcessor msgFileProcessor = new MSGFileProcessor(input)
            {
                IsSinglePDFOutput = false,
                WaitTimeinMilliSeconds = ConversionSettings.WaitTimeInMilliSeconds,
                FailureAttemptCount = ConversionSettings.FailureAttemptCount
            };
            var (converted, message, output, attachments) = msgFileProcessor.ConvertToPDF();
            return (output, attachments);
        }

        //private static Stream convertEMLFiles(Stream input)
        //{
        //    EMLFileProcessor emlFileProcessor = new EMLFileProcessor(input, "C:\\test-files\\test-payment.eml", "test-payment");
        //    emlFileProcessor.IsSinglePDFOutput = false;
        //    emlFileProcessor.WaitTimeinMilliSeconds = ConversionSettings.WaitTimeInMilliSeconds;
        //    emlFileProcessor.FailureAttemptCount = ConversionSettings.FailureAttemptCount;
        //    emlFileProcessor.HTMLtoPdfWebkitPath = ConversionSettings.HTMLtoPdfWebkitPath;
        //    var (converted, message, PdfOutputFilePath, output) = emlFileProcessor.ConvertToPDF();
        //    return output;
        //}

        private static Stream ConvertDocFiles(Stream input)
        {
            DocFileProcessor docFileProcessor = new DocFileProcessor(input)
            {
                IsSinglePDFOutput = false,
                WaitTimeinMilliSeconds = ConversionSettings.WaitTimeInMilliSeconds,
                FailureAttemptCount = ConversionSettings.FailureAttemptCount
            };
            var (converted, output) = docFileProcessor.ConvertToPDF();
            return output;
        }


        private static async System.Threading.Tasks.Task<S3AccessKeys> getAccessKeyFromDB(string bucket)
        {
            S3AccessKeys s3AccessKeys = new S3AccessKeys();
            try
            {
                var host = Environment.GetEnvironmentVariable("DATABASE_HOST");
                var port = Environment.GetEnvironmentVariable("DATABASE_PORT");
                var dbname = Environment.GetEnvironmentVariable("DATABASE_NAME");
                var username = Environment.GetEnvironmentVariable("DATABASE_USERNAME");
                var password = Environment.GetEnvironmentVariable("DATABASE_PASSWORD");
                var connString = "Host="+host + ";Port=" + port + ";Username="+username+"; Password="+password+";Database="+dbname+";";


                await using var conn = new NpgsqlConnection(connString);
                await conn.OpenAsync();

                // Retrieve access key
                await using (var cmd = new NpgsqlCommand("SELECT attributes FROM \"DocumentPathMapper\" where bucket='"+bucket+"';", conn))
                await using (var reader = await cmd.ExecuteReaderAsync())
                {
                    while (await reader.ReadAsync())
                    {
                        string res = reader.GetString(0);
                        Console.WriteLine(res);
                        s3AccessKeys = JsonSerializer.Deserialize<S3AccessKeys>(res);
                    }


                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($" Error happpened while accessing DB. Exception message : {ex.Message} , StackTrace :{ex.StackTrace}");
            }
            return s3AccessKeys;
        }

    }
}