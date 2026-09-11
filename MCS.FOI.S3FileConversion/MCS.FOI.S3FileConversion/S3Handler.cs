using Amazon;
using Amazon.Runtime;
using Amazon.S3;
using Amazon.S3.Model;
using MCS.FOI.CalendarToPDF;
using MCS.FOI.DocToPDF;
using MCS.FOI.PPTToPDF;
using MCS.FOI.ExcelToPDF;
using MCS.FOI.MSGToPDF;
using MCS.FOI.S3FileConversion.Utilities;
using Microsoft.Extensions.Configuration;
using Serilog;
using StackExchange.Redis;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Linq;

namespace MCS.FOI.S3FileConversion
{
    internal class S3AccessKeys
    {
        public string s3accesskey { get; set; }
        public string s3secretkey { get; set; }
    }
    internal class S3Handler : IFileConverter
    {
        Stream? output = null;
        Dictionary<MemoryStream, Dictionary<string, string>> attachments = null;
        ExtractedAttachmentSet? msgAttachments;
        ExcelFileProcessor excelFileProcessor = null;
        DocFileProcessor docFileProcessor = null;
        PptFileProcessor pptFileProcessor = null;
        MSGFileProcessor msgFileProcessor = null;
        CalendarFileProcessor calendarFileProcessor = null;
        List<Dictionary<string, string>> returnAttachments = null;
        public S3Handler() { }


        public async System.Threading.Tasks.Task<(List<Dictionary<string, string>>, long)> ConvertFile(StreamEntry message, S3AccessKeys s3AccessKeys)
        {
            var filePath = (string)message["s3filepath"];
            // Get S3 Access credentials based on ministry
            //var cb = new ConfigurationBuilder().AddJsonFile($"s3access.json", true, true).AddEnvironmentVariables().Build();
            //string bucket = filePath.Split("/")[3];
            // Comment in if running locally
            //string S3Host = cb.GetSection("S3Host").Value;
            //string S3AccessKeyID = cb.GetSection($"AccountMapping:{bucket}:S3AccessKeyID").Value;
            //string S3AccessSecretKey = cb.GetSection($"AccountMapping:{bucket}:S3AccessSecretKey").Value;
            //string S3ServiceAccount = cb.GetSection($"AccountMapping:{bucket}:S3ServiceAccount").Value;
            //S3AccessKeys s3AccessKeys = await DBHandler.getAccessKeyFromDB(bucket);
            string S3AccessKeyID = s3AccessKeys.s3accesskey;
            string S3AccessSecretKey = s3AccessKeys.s3secretkey;


            returnAttachments = new();
            long convertedSize;
            using var client = new HttpClient();

            try
            {
                using (FOIS3ObjectStorageClient fOIS3ObjectStorageClient = new FOIS3ObjectStorageClient(S3AccessKeyID, S3AccessSecretKey))
                {
                    using (IAmazonS3 s3 = fOIS3ObjectStorageClient.getS3Client())
                    {

                        string S3Host = fOIS3ObjectStorageClient.gets3host();
                        // Get File from s3
                        var fileKey = filePath.Split(S3Host + '/')[1];
                        var presignedGetURL = GetPresignedURL(s3, fileKey, HttpVerb.GET);

                        Log.Information("Fetching file from S3");
                        using HttpResponseMessage response = await client.GetAsync(presignedGetURL);
                        response.EnsureSuccessStatusCode();
                        using Stream responseStream = await response.Content.ReadAsStreamAsync();
                        Log.Information("Successfully fetched file from S3");
                        // Convert File
                        string extension = Path.GetExtension(fileKey).ToLower();

                        output = new MemoryStream();
                        attachments = new();
                        Log.Information("Starting conversion of {extension} file", extension);
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
                                (output, msgAttachments) = ConvertMSGFiles(responseStream);
                                break;
                            case ".doc":
                            case ".docx":
                                output = ConvertDocFiles(responseStream);
                                break;
                            case ".ppt":
                            case ".pptx":
                                output = ConvertPptFiles(responseStream);
                                break;
                        }

                        Log.Information("Conversion complete, converted filesize: {ConvertedBytes} bytes", output.Length);

                        // Save converted pdf back to s3
                        var newKey = Path.ChangeExtension(fileKey, ".pdf");
                        var presignedPutURL = GetPresignedURL(s3, newKey, HttpVerb.PUT);

                        Log.Information("Uploading converted file to S3: {NewKey}", newKey);
                        output.Position = 0;
                        convertedSize = output.Length;
                        using (StreamContent strm = new(output))
                        {
                            strm.Headers.ContentType = new System.Net.Http.Headers.MediaTypeHeaderValue("application/octet-stream");
                            using HttpResponseMessage putRespMsg = await client.PutAsync(presignedPutURL, strm);
                            putRespMsg.EnsureSuccessStatusCode();
                            Log.Information("Successfully uploaded converted file: {NewKey}", newKey);

                            var uploadAttachments = new List<(Func<Stream> OpenRead, Dictionary<string, string> Metadata, Action Uploaded)>();
                            if (attachments != null)
                            {
                                foreach (var attachment in attachments)
                                {
                                    uploadAttachments.Add((
                                        () =>
                                        {
                                            attachment.Key.Position = 0;
                                            return attachment.Key;
                                        },
                                        attachment.Value,
                                        () => { }));
                                }
                            }

                            if (msgAttachments != null)
                            {
                                foreach (var attachment in msgAttachments)
                                {
                                    uploadAttachments.Add((
                                        attachment.OpenRead,
                                        attachment.Metadata,
                                        () => File.Delete(attachment.TemporaryFilePath)));
                                }
                            }

                            var attachmentIndex = 0;
                            foreach (var attachment in uploadAttachments)
                            {
                                    var attributes = JsonSerializer.Deserialize<JsonNode>((string)message["attributes"]);
                                    attributes["filesize"] = JsonValue.Create(attachment.Metadata["size"]);
                                    attributes["isattachment"] = JsonValue.Create(true);
                                    attributes["rootparentfilepath"] ??= JsonValue.Create((string)message["s3filepath"]);
                                    if (attachment.Metadata.ContainsKey("lastmodified"))
                                    {
                                        attributes["lastmodified"] = JsonValue.Create(attachment.Metadata["lastmodified"]);
                                    }
                                    string attachmentExtension = Path.GetExtension(attachment.Metadata["filename"]);
                                    attributes["extension"] = JsonValue.Create(attachmentExtension);
                                    attachment.Metadata.Add("extension", attachmentExtension);
                                    string[] formats = ConversionSettings.ConversionFormats.Concat(ConversionSettings.DedupeFormats).Except(ConversionSettings.IncompatibleFormats).ToArray();
                                    attributes["incompatible"] = JsonValue.Create(Array.IndexOf(formats, attachmentExtension.ToLower()) == -1);
                                    attachment.Metadata.Add("attributes", attributes.ToJsonString());
                                    var parentFolder = attributes["rootparentfilepath"] == null ? newKey : attributes["rootparentfilepath"].ToString().Split(S3Host + '/')[1];
                                    var newAttachmentKey = GetAttachmentKey(
                                        parentFolder,
                                        (int) message["jobid"],
                                        attachmentIndex++,
                                        attachmentExtension);
                                    var attachmentPresignedPutURL = GetPresignedURL(s3, newAttachmentKey, HttpVerb.PUT);
                                    attachment.Metadata.Add("filepath", S3Host + "/" + newAttachmentKey);
                                    returnAttachments.Add(attachment.Metadata);
                                    Log.Information("Uploading attachment {Filename} to S3: {AttachmentKey}", attachment.Metadata["filename"], newAttachmentKey);
                                    using (var attachmentContent = attachment.OpenRead())
                                    using (StreamContent attachmentstrm = new StreamContent(attachmentContent))
                                    {
                                        attachmentstrm.Headers.ContentType = new System.Net.Http.Headers.MediaTypeHeaderValue("application/octet-stream");
                                        using (HttpResponseMessage attachementresponse = await client.PutAsync(attachmentPresignedPutURL, attachmentstrm))
                                        {
                                            attachementresponse.EnsureSuccessStatusCode();
                                            Log.Information("Successfully uploaded attachment: {AttachmentKey}", newAttachmentKey);
                                        }
                                    }
                                    attachment.Uploaded();
                            }
                        }

                    }

                }
            }
            catch (AmazonS3Exception s3ex)
            {
                Console.WriteLine($"Error encountered on server. Message:'{s3ex.Message}' getting list of objects.");
                Log.Error(s3ex, "S3 error processing file");
                throw s3ex;
            }
            catch (Exception exception)
            {
                Console.WriteLine($"Error encountered on server. Message:'{exception.Message}' getting list of objects.");
                Log.Error(exception, "Error processing file");
                throw;
            }
            finally
            {
                client.Dispose();
            }
            return (returnAttachments, convertedSize);
        }

        public string GetPresignedURL(IAmazonS3 s3, string fileName, HttpVerb method)
        {
            AWSConfigsS3.UseSignatureVersion4 = true;
            var serviceUri = new Uri(s3.Config.ServiceURL);
            GetPreSignedUrlRequest request = new()
            {
                Key = fileName,
                Verb = method,
                Expires = DateTime.Now.AddHours(1),
                Protocol = serviceUri.Scheme == Uri.UriSchemeHttp ? Protocol.HTTP : Protocol.HTTPS,
            };
            return s3.GetPreSignedURL(request);
        }

        private Stream ConvertExcelFiles(Stream input)
        {
            excelFileProcessor = new ExcelFileProcessor(input)
            {
                IsSinglePDFOutput = true,
                WaitTimeinMilliSeconds = ConversionSettings.WaitTimeInMilliSeconds,
                FailureAttemptCount = ConversionSettings.FailureAttemptCount,
                OpenFileWaitTimeInSeconds = ConversionSettings.OpenFileWaitTimeInSeconds
            };
            
            var (converted, message, output) = excelFileProcessor.ConvertToPDF();
            
                
            return output;
        }

        private (Stream, Dictionary<MemoryStream, Dictionary<string, string>>) ConvertCalendarFiles(Stream input)
        {
             calendarFileProcessor = new CalendarFileProcessor(input)
            {
                WaitTimeinMilliSeconds = ConversionSettings.WaitTimeInMilliSeconds,
                FailureAttemptCount = ConversionSettings.FailureAttemptCount
            };
            var (isProcessed, Message, output, attachments) = calendarFileProcessor.ProcessCalendarFiles();
            return (output, attachments);
        }

        private (Stream, ExtractedAttachmentSet) ConvertMSGFiles(Stream input)
        {
             msgFileProcessor = new MSGFileProcessor(input)
            {
                IsSinglePDFOutput = false,
                WaitTimeinMilliSeconds = ConversionSettings.WaitTimeInMilliSeconds,
                FailureAttemptCount = ConversionSettings.FailureAttemptCount
            };
            var (converted, message, output, attachments) = msgFileProcessor.ConvertToPDF();
            return (output, attachments);
        }


        private Stream ConvertDocFiles(Stream input)
        {
             docFileProcessor = new DocFileProcessor(input)
            {
                IsSinglePDFOutput = false,
                WaitTimeinMilliSeconds = ConversionSettings.WaitTimeInMilliSeconds,
                FailureAttemptCount = ConversionSettings.FailureAttemptCount
            };
            var (converted, output) = docFileProcessor.ConvertToPDF();
            return output;
        }

        private Stream ConvertPptFiles(Stream input)
        {
            pptFileProcessor = new PptFileProcessor(input)
            {
                IsSinglePDFOutput = false,
                WaitTimeinMilliSeconds = ConversionSettings.WaitTimeInMilliSeconds,
                FailureAttemptCount = ConversionSettings.FailureAttemptCount
            };
            var (converted, output) = pptFileProcessor.ConvertToPDF();
            return output;
        }


        internal static string GetAttachmentKey(
            string parentFolder,
            int jobId,
            int attachmentIndex,
            string extension) =>
            $"{parentFolder.Split('.')[0]}/{jobId}-{attachmentIndex}{extension}";

        public void Dispose()
        {
            Dispose(true);
            GC.SuppressFinalize(this);
        }

        protected virtual void Dispose(bool disposing)
        {
            if (disposing)
            {
                if (output != null)
                    output.Dispose();

                if(excelFileProcessor!=null)
                    excelFileProcessor.Dispose();

                if (docFileProcessor != null)
                    docFileProcessor.Dispose();

                if (msgFileProcessor != null)
                    msgFileProcessor.Dispose();

                msgAttachments?.Dispose();
                msgAttachments = null;

                if (calendarFileProcessor != null)
                    calendarFileProcessor.Dispose();

                if (pptFileProcessor != null)
                    pptFileProcessor.Dispose();

                attachments = null;
                returnAttachments = null;
                // free managed resources
            }
           
        }

    }
}
