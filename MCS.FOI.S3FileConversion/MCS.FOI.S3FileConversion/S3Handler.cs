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
        public static async Task<List<string>> ConvertFile(string? filePath)
        {
            List<string> attachmentKeys = new();
            if (!string.IsNullOrEmpty(filePath))
            {
                // Get S3 Access credentials based on ministry
                IConfigurationRoot cb = new ConfigurationBuilder().AddJsonFile($"s3access.json", true, true).AddEnvironmentVariables().Build();
                //var configurationbuilder = new ConfigurationBuilder()
                //            .AddJsonFile($"appsettings.json", true, true)
                //            .AddEnvironmentVariables().Build();
                string S3Host = cb.GetSection("S3Host").Value;
                string bucket = filePath.Split("/")[3];
                string S3AccessKeyID = cb.GetSection($"AccountMapping:{bucket}:S3AccessKeyID").Value;
                string S3AccessSecretKey = cb.GetSection($"AccountMapping:{bucket}:S3AccessSecretKey").Value;
                //string S3ServiceAccount = cb.GetSection($"AccountMapping:{bucket}:S3ServiceAccount").Value;
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
                                attachment.Key.Position = 0;
                                var newAttachmentKey = bucket + "/" + folder + "/" + attachment.Value;
                                var attachmentPresignedPutURL = GetPresignedURL(s3, newAttachmentKey, HttpVerb.PUT);
                                attachmentKeys.Add(S3Host + "/" + newAttachmentKey);
                                StreamContent attachmentstrm = new(attachment.Key);
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
            ExcelFileProcessor excelFileProcessor = new(input)
            {
                IsSinglePDFOutput = false,
                WaitTimeinMilliSeconds = ConversionSettings.WaitTimeInMilliSeconds,
                FailureAttemptCount = ConversionSettings.FailureAttemptCount
            };
            (bool converted, string message, Stream output) = excelFileProcessor.ConvertToPDF();
            if (!converted)
            {
                string error = $"Exception Occured while coverting Excel file to PDF, error :  {message}";
                Console.WriteLine(error);
            }
            return output;
        }

        private static (Stream, Dictionary<MemoryStream, string>) ConvertCalendarFiles(Stream input)
        {
            CalendarFileProcessor calendarFileProcessor = new(input)
            {
                WaitTimeinMilliSeconds = ConversionSettings.WaitTimeInMilliSeconds,
                FailureAttemptCount = ConversionSettings.FailureAttemptCount
            };
            (bool isProcessed, string Message, Stream output, Dictionary<MemoryStream, string> attachments) = calendarFileProcessor.ProcessCalendarFiles();
            if (!isProcessed)
            {
                string error = $"Exception Occured while coverting ICS file to PDF, error :  {Message}";
                Console.WriteLine(error);
            }
            return (output, attachments);
        }

        private static (Stream, Dictionary<MemoryStream, string>) ConvertMSGFiles(Stream input)
        {
            MSGFileProcessor msgFileProcessor = new(input)
            {
                IsSinglePDFOutput = false,
                WaitTimeinMilliSeconds = ConversionSettings.WaitTimeInMilliSeconds,
                FailureAttemptCount = ConversionSettings.FailureAttemptCount
            };
            (bool converted, string message, Stream output, Dictionary<MemoryStream, string> attachments) = msgFileProcessor.ConvertToPDF();
            if (!converted)
            {
                string error = $"Exception Occured while coverting MSG file to PDF, error :  {message}";
                Console.WriteLine(error);
            }
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
            DocFileProcessor docFileProcessor = new(input)
            {
                IsSinglePDFOutput = false,
                WaitTimeinMilliSeconds = ConversionSettings.WaitTimeInMilliSeconds,
                FailureAttemptCount = ConversionSettings.FailureAttemptCount
            };
            (bool converted, string message, Stream output) = docFileProcessor.ConvertToPDF();
            if (!converted) {
                string error = $"Exception Occured while coverting Doc/Docx file to PDF, error :  {message}";
                Console.WriteLine(error);
            }
            return output;
        }

    }
}