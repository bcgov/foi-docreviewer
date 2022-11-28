using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
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


namespace MCS.FOI.S3FileConversion
{
    internal class S3Handler
    {
        public static async System.Threading.Tasks.Task<List<String>> convertFile(string filePath)
        {
            // Get S3 Access credentials based on ministry
            var cb = new ConfigurationBuilder().AddJsonFile($"s3access.json", true, true).AddEnvironmentVariables().Build();
            var configurationbuilder = new ConfigurationBuilder()
                        .AddJsonFile($"appsettings.json", true, true)
                        .AddEnvironmentVariables().Build();
            string S3Host = cb.GetSection("S3Host").Value;
            string bucket = filePath.Split("/")[3];
            string S3AccessKeyID = cb.GetSection($"AccountMapping:{bucket}:S3AccessKeyID").Value;
            string S3AccessSecretKey = cb.GetSection($"AccountMapping:{bucket}:S3AccessSecretKey").Value;
            string S3ServiceAccount = cb.GetSection($"AccountMapping:{bucket}:S3ServiceAccount").Value;
            
            List<string> attachmentKeys = new List<string>();
            try
            {
                // Initialize S3 Client
                IAmazonS3 s3;
                AWSCredentials AWSCredentials = new BasicAWSCredentials(S3AccessKeyID, S3AccessSecretKey);
                AmazonS3Config config = new AmazonS3Config
                {
                    ServiceURL = S3Host
                };

                AmazonS3Client s3Client = new AmazonS3Client(AWSCredentials, config);

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
                    Dictionary<MemoryStream, string> attachments = new Dictionary<MemoryStream, string>();

                    switch (extension)
                    {
                        case ".xls":
                        case ".xlsx":
                            output = convertExcelFiles(responseStream);
                            break;
                        case ".ics":
                            (output, attachments) = convertCalendarFiles(responseStream);
                            break;
                        case ".msg":
                            (output, attachments) = convertMSGFiles(responseStream);
                            break;
                        //case ".eml":
                        //    output = convertEMLFiles(responseStream);
                        //    break;
                        case ".doc":
                        case ".docx":
                            output = convertDocFiles(responseStream);
                            break;
                    }


                    // Save converted pdf back to s3
                    var newKey = Path.ChangeExtension(fileKey, ".pdf");
                    var presignedPutURL = GetPresignedURL(s3, newKey, HttpVerb.PUT);

                    output.Position = 0;
                    StreamContent strm = new StreamContent(output);
                    strm.Headers.ContentType = new System.Net.Http.Headers.MediaTypeHeaderValue("application/octet-stream");
                    HttpResponseMessage putRespMsg = await client.PutAsync(presignedPutURL, strm);
                    
                    if (attachments != null && attachments.Count > 0)
                    {
                        foreach (KeyValuePair<MemoryStream, string> attachment in attachments)
                        {
                            attachment.Key.Position=0;
                            var newAttachmentKey = bucket + "/"+ attachment.Value;
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

        private static Stream convertExcelFiles(Stream input)
        {
            ExcelFileProcessor excelFileProcessor = new ExcelFileProcessor(input);
            excelFileProcessor.IsSinglePDFOutput = false;
            excelFileProcessor.WaitTimeinMilliSeconds = ConversionSettings.WaitTimeInMilliSeconds;
            excelFileProcessor.FailureAttemptCount = ConversionSettings.FailureAttemptCount;
            var (converted, message, output) = excelFileProcessor.ConvertToPDF();
            return output;
        }

        private static (Stream, Dictionary<MemoryStream, string>) convertCalendarFiles(Stream input)
        {
            CalendarFileProcessor calendarFileProcessor = new CalendarFileProcessor(input);
            calendarFileProcessor.WaitTimeinMilliSeconds = ConversionSettings.WaitTimeInMilliSeconds;
            calendarFileProcessor.FailureAttemptCount = ConversionSettings.FailureAttemptCount;
            calendarFileProcessor.HTMLtoPdfWebkitPath = ConversionSettings.HTMLtoPdfWebkitPath;
            var (isProcessed, Message, output, attachments) = calendarFileProcessor.ProcessCalendarFiles();
            return (output, attachments);
        }

        private static (Stream, Dictionary<MemoryStream, string>) convertMSGFiles(Stream input)
        {
            MSGFileProcessor msgFileProcessor = new MSGFileProcessor(input);
            msgFileProcessor.IsSinglePDFOutput = false;
            msgFileProcessor.WaitTimeinMilliSeconds = ConversionSettings.WaitTimeInMilliSeconds;
            msgFileProcessor.FailureAttemptCount = ConversionSettings.FailureAttemptCount;
            msgFileProcessor.HTMLtoPdfWebkitPath = ConversionSettings.HTMLtoPdfWebkitPath;
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

        private static Stream convertDocFiles(Stream input)
        {
            DocFileProcessor docFileProcessor = new DocFileProcessor(input);
            docFileProcessor.IsSinglePDFOutput = false;
            docFileProcessor.WaitTimeinMilliSeconds = ConversionSettings.WaitTimeInMilliSeconds;
            docFileProcessor.FailureAttemptCount = ConversionSettings.FailureAttemptCount;
            var (converted, output) = docFileProcessor.ConvertToPDF();
            return output;
        }

    }
}