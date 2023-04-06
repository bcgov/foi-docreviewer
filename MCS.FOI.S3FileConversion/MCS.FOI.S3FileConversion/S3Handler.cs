using Amazon;
using Amazon.Runtime;
using Amazon.S3;
using Amazon.S3.Model;
using MCS.FOI.CalendarToPDF;
using MCS.FOI.DocToPDF;
using MCS.FOI.ExcelToPDF;
using MCS.FOI.MSGToPDF;
using MCS.FOI.S3FileConversion.Utilities;
using Microsoft.Extensions.Configuration;
using StackExchange.Redis;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace MCS.FOI.S3FileConversion
{
    internal class S3AccessKeys
    {
        public string s3accesskey { get; set; }
        public string s3secretkey { get; set; }
    }
    internal class S3Handler
    {
        public static async System.Threading.Tasks.Task<List<Dictionary<string, string>>> ConvertFile(StreamEntry message)
        {
            var filePath = (string)message["s3filepath"];
            // Get S3 Access credentials based on ministry
            var cb = new ConfigurationBuilder().AddJsonFile($"s3access.json", true, true).AddEnvironmentVariables().Build();
            string bucket = filePath.Split("/")[3];
            // Comment in if running locally
            //string S3Host = cb.GetSection("S3Host").Value;
            //string S3AccessKeyID = cb.GetSection($"AccountMapping:{bucket}:S3AccessKeyID").Value;
            //string S3AccessSecretKey = cb.GetSection($"AccountMapping:{bucket}:S3AccessSecretKey").Value;
            //string S3ServiceAccount = cb.GetSection($"AccountMapping:{bucket}:S3ServiceAccount").Value;
            S3AccessKeys s3AccessKeys = await DBHandler.getAccessKeyFromDB(bucket);
            string S3AccessKeyID = s3AccessKeys.s3accesskey;
            string S3AccessSecretKey = s3AccessKeys.s3secretkey;
            string S3Host = Environment.GetEnvironmentVariable("S3_HOST");
            if (!S3Host.Contains("https://"))
            {
                S3Host = "https://" + S3Host;
            }

            List<Dictionary<string, string>> returnAttachments = new();
            Stream output = new MemoryStream();
            var client = new HttpClient();
            try
            {
                // Initialize S3 Client
                IAmazonS3 s3;
                AWSCredentials AWSCredentials = new BasicAWSCredentials(S3AccessKeyID, S3AccessSecretKey);
                AmazonS3Config config = new()
                {
                    ServiceURL = S3Host
                };

                using (s3 = new AmazonS3Client(AWSCredentials, config))
                {
                    // Get File from s3
                    var fileKey = filePath.Split(S3Host + '/')[1];
                    var presignedGetURL = GetPresignedURL(s3, fileKey, HttpVerb.GET);


                    using HttpResponseMessage response = await client.GetAsync(presignedGetURL);
                    response.EnsureSuccessStatusCode();
                    using Stream responseStream = response.Content.ReadAsStream();

                    // Convert File
                    string extension = Path.GetExtension(fileKey);


                    Dictionary<MemoryStream, Dictionary<string, string>> attachments = new();


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
                        case ".doc":
                        case ".docx":
                            output = ConvertDocFiles(responseStream);
                            break;
                    }


                    // Save converted pdf back to s3
                    var newKey = Path.ChangeExtension(fileKey, ".pdf");
                    var presignedPutURL = GetPresignedURL(s3, newKey, HttpVerb.PUT);

                    output.Position = 0;
                    using (StreamContent strm = new(output))
                    {
                        strm.Headers.ContentType = new System.Net.Http.Headers.MediaTypeHeaderValue("application/octet-stream");
                        using HttpResponseMessage putRespMsg = await client.PutAsync(presignedPutURL, strm);

                        if (attachments != null && attachments.Count > 0)
                        {
                            foreach (KeyValuePair<MemoryStream, Dictionary<string, string>> attachment in attachments)
                            {
                                attachment.Key.Position = 0;
                                var attributes = JsonSerializer.Deserialize<JsonNode>(message["attributes"]);
                                attributes["filesize"] = JsonValue.Create(attachment.Value["size"]);
                                attributes["isattachment"] = JsonValue.Create(true);
                                attributes["rootparentfilepath"] ??= JsonValue.Create((string)message["s3filepath"]);
                                if (attachment.Value.ContainsKey("lastmodified"))
                                {
                                    attributes["lastmodified"] = JsonValue.Create(attachment.Value["lastmodified"]);
                                }
                                string attachmentExtension = Path.GetExtension(attachment.Value["filename"]);
                                attributes["extension"] = JsonValue.Create(attachmentExtension);
                                attachment.Value.Add("extension", attachmentExtension);
                                string[] formats = { ".doc", ".docx", ".xls", ".xlsx", ".ics", ".msg", ".pdf" };
                                attributes["incompatible"] = JsonValue.Create(Array.IndexOf(formats, attachmentExtension) == -1);
                                attachment.Value.Add("attributes", attributes.ToJsonString());
                                var parentFolder = attributes["rootparentfilepath"] == null ? newKey : attributes["rootparentfilepath"].ToString().Split(S3Host + '/')[1];
                                var newAttachmentKey = parentFolder.Split(".")[0] + "/" + attachment.Value["s3filename"];
                                var attachmentPresignedPutURL = GetPresignedURL(s3, newAttachmentKey, HttpVerb.PUT);
                                attachment.Value.Add("filepath", S3Host + "/" + newAttachmentKey);
                                returnAttachments.Add(attachment.Value);
                                using (StreamContent attachmentstrm = new StreamContent(attachment.Key))
                                {
                                    attachmentstrm.Headers.ContentType = new System.Net.Http.Headers.MediaTypeHeaderValue("application/octet-stream");
                                    using (HttpResponseMessage attachementresponse = await client.PutAsync(attachmentPresignedPutURL, attachmentstrm))
                                    {
                                        attachementresponse.EnsureSuccessStatusCode();
                                    }
                                    
                                }

                            }
                        }
                    }



                }
            }
            catch (AmazonS3Exception s3ex)
            {
                Console.WriteLine($"Error encountered on server. Message:'{s3ex.Message}' getting list of objects.");
                throw s3ex;
            }
            catch (Exception exception)
            {
                Console.WriteLine($"Error encountered on server. Message:'{exception.Message}' getting list of objects.");
                throw exception;
            }
            finally
            {
                client.Dispose();
                output.Dispose();
            }
            return returnAttachments;
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
                IsSinglePDFOutput = true,
                WaitTimeinMilliSeconds = ConversionSettings.WaitTimeInMilliSeconds,
                FailureAttemptCount = ConversionSettings.FailureAttemptCount
            };
            var (converted, message, output) = excelFileProcessor.ConvertToPDF();
            return output;
        }

        private static (Stream, Dictionary<MemoryStream, Dictionary<string, string>>) ConvertCalendarFiles(Stream input)
        {
            CalendarFileProcessor calendarFileProcessor = new CalendarFileProcessor(input)
            {
                WaitTimeinMilliSeconds = ConversionSettings.WaitTimeInMilliSeconds,
                FailureAttemptCount = ConversionSettings.FailureAttemptCount
            };
            var (isProcessed, Message, output, attachments) = calendarFileProcessor.ProcessCalendarFiles();
            return (output, attachments);
        }

        private static (Stream, Dictionary<MemoryStream, Dictionary<string, string>>) ConvertMSGFiles(Stream input)
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

    }
}