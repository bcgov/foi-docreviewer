using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading;
using MsgReader;
using MsgReader.Outlook;
using RtfPipe.Tokens;
using Serilog;
using Syncfusion.HtmlConverter;
using Syncfusion.Pdf;
using Syncfusion.Pdf.Graphics;

namespace MCS.FOI.MSGAttachmentsToPdf
{
    public class MSGFileProcessor : IMSGFileProcessor
    {
        public string MSGSourceFilePath { get; set; }
        public Stream SourceStream { get; set; }
        public string OutputFilePath { get; set; }
        public string MSGFileName { get; set; }
        public bool IsSinglePDFOutput { get; set; }
        public int FailureAttemptCount { get; set; }
        public int WaitTimeinMilliSeconds { get; set; }

        public string HTMLtoPdfWebkitPath { get; set; }

        public string DestinationPath { get; set; }



        public MSGFileProcessor() { }


        public MSGFileProcessor(Stream sourceStream, string destinationPath, string fileName)
        {
            //this.MSGSourceFilePath = sourcePath;
            this.DestinationPath = destinationPath;
            this.MSGFileName = fileName;
            this.SourceStream = sourceStream;

        }

        //public (bool, string, string, Stream) ProcessMsgOrEmlFiles()
        //{
        //    MemoryStream output = new MemoryStream();
        //    bool isProcessed;

        //    try
        //    {
        //        string htmlString = ConvertMsgOrEmlToHTML();
        //        output = ConvertHTMLtoPDF(htmlString, output);
        //    }
        //    catch (Exception ex)
        //    {
        //        throw ex;
        //    }
        //    return (isProcessed, Message, DestinationPath, output);
        //}



        public (bool, string, string, Stream) MoveAttachments()
        {
            var message = $"No attachments to move to output folder";
            bool moved = true;
            string outputpath = string.Empty;
            MemoryStream output = new MemoryStream();
            try
            {
                //string sourceFile = Path.Combine(MSGSourceFilePath, MSGFileName);
                Dictionary<string, Object> problematicFiles = null;

                //if (File.Exists(sourceFile))
                //{

                    for (int attempt = 1; attempt < FailureAttemptCount; attempt++)
                    {

                        try
                        {

                            using (var msg = new MsgReader.Outlook.Storage.Message(SourceStream))
                            {
                            //var bodyHtml = msg.BodyHtml;

                                string htmlString = generateHtmlfromMsg(msg);
                                output = ConvertHTMLtoPDF(htmlString, output);

                                var attachments = msg.Attachments;
                                foreach (Object attachment in attachments)
                                {
                                    var type = attachment.GetType().FullName;
                                    if (type.ToLower().Contains("message"))
                                    {
                                        var file = (Storage.Message)attachment;
                                        problematicFiles = problematicFiles == null ? new Dictionary<string, Object>() : problematicFiles;
                                        problematicFiles.Add(file.FileName, file);

                                    }
                                    else
                                    {
                                        var file = (Storage.Attachment)attachment;
                                        if (file.FileName.ToLower().Contains(".xls") || file.FileName.ToLower().Contains(".ics") || file.FileName.ToLower().Contains(".msg") || file.FileName.ToLower().Contains(".png"))
                                        {
                                            problematicFiles = problematicFiles == null ? new Dictionary<string, Object>() : problematicFiles;
                                            problematicFiles.Add(file.FileName, file);

                                        }

                                    }
                                }

                                if (problematicFiles != null)
                                {
                                    int cnt = 0;
                                    foreach (var attachmenttomove in problematicFiles)
                                    {

                                        if (attachmenttomove.Key.ToLower().Contains(".msg"))
                                        {
                                            var _attachment = (Storage.Message)attachmenttomove.Value;
                                            string fileName = @$"{OutputFilePath}\msgattachments\{Path.GetFileNameWithoutExtension(MSGFileName)}_{_attachment.FileName}";
                                            foreach (var subattachment in _attachment.Attachments)
                                            {
                                                var type = subattachment.GetType().FullName;
                                                if (type.ToLower().Contains("attachment"))
                                                {
                                                    var file = (Storage.Attachment)subattachment;
                                                    CreateOutputFolder("subattachments");
                                                    string _fileName = @$"{OutputFilePath}\msgattachments\subattachments\{Path.GetFileNameWithoutExtension(MSGFileName)}_{file.FileName}";
                                                    File.WriteAllBytes(_fileName, file.Data);

                                                }

                                            }

                                        }
                                        else
                                        {
                                            var _attachment = (Storage.Attachment)attachmenttomove.Value;
                                            string fileName = @$"{OutputFilePath}\msgattachments\{Path.GetFileNameWithoutExtension(MSGFileName)}_{_attachment.FileName}";
                                            CreateOutputFolder();
                                            File.WriteAllBytes(fileName, _attachment.Data);
                                            outputpath += fileName;
                                        }

                                        cnt++;

                                    }
                                    moved = true;
                                    message = string.Concat($"{cnt} problematic files moved", outputpath);
                                }

                            break;
                            }
                        }
                        catch(Exception e)
                        {
                            message = $"Exception happened while accessing File {SourceStream}, re-attempting count : {attempt} , Error Message : {e.Message} , Stack trace : {e.StackTrace}";
                            Log.Error(message);
                            Console.WriteLine(message);                            
                            Thread.Sleep(WaitTimeinMilliSeconds);
                        }
                    }
                //}
                //else
                //{
                //    message = $"{sourceFile} does not exist!";
                //    Log.Error(message);
                //}
            }
            catch (Exception ex)
            {
                Log.Error($"Error happened while moving attachments on {MSGSourceFilePath}\\{MSGFileName} , Exception message : {ex.Message} , details : {ex.StackTrace}");
                message = $"Error happened while moving attachments on {MSGSourceFilePath}\\{MSGFileName} , Exception message : {ex.Message} , details : {ex.StackTrace}";
                moved = false;
            }

            return (moved, message, outputpath, output);
        }


        private string generateHtmlfromMsg(Storage.Message msg)
        {
            var sb = new StringBuilder();
            var from = msg.Sender;
            var sentOn = msg.SentOn;
            //var recipientsTo = msg.GetEmailRecipients(
            //    MsgReader.Outlook.Storage.Recipient.RecipientType.To, false, false);
            //var recipientsCc = msg.GetEmailRecipients(
            //    MsgReader.Outlook.Storage.Recipient.RecipientType.Cc, false, false);
            //var recipientsBCC = msg.GetEmailRecipients(
            //    MsgReader.Outlook.Storage.Recipient.RecipientType.Bcc, false, false);
            var subject = msg.Subject;

            sb.AppendLine($"   From: {from.DisplayName} {from.Email}");
            sb.AppendLine($"   Sent: {sentOn}");
            //sb.AppendLine($"     To: {recipientsTo}");
            //sb.AppendLine($"     CC: {recipientsCc}");
            //sb.AppendLine($"    BCC: {recipientsBCC}");
            sb.AppendLine($"Subject: {subject}");
            sb.AppendLine($"   Body:");
            sb.AppendLine(msg.BodyText);
            //File.WriteAllText(Path.Combine(
            //    AppDomain.CurrentDomain.BaseDirectory, "suggestion.txt"),
            //    sb.ToString());
            return sb.ToString();
        }

        private MemoryStream ConvertHTMLtoPDF(string strHTML, MemoryStream output)
        {
            bool isConverted;
            FileStream fileStream = null;
            try
            {
                //Initialize HTML to PDF converter with Blink rendering engine
                HtmlToPdfConverter htmlConverter = new HtmlToPdfConverter(HtmlRenderingEngine.WebKit);

                WebKitConverterSettings webKitConverterSettings = new WebKitConverterSettings() { EnableHyperLink = true };

                //Point to the webkit based on the platform the application is running
                webKitConverterSettings.WebKitPath = HTMLtoPdfWebkitPath;


                //Assign WebKit converter settings to HTML converter
                htmlConverter.ConverterSettings = webKitConverterSettings;
                htmlConverter.ConverterSettings.Margin.All = 25;
                htmlConverter.ConverterSettings.EnableHyperLink = true;
                htmlConverter.ConverterSettings.PdfPageSize = PdfPageSize.A4;

                //Convert HTML string to PDF
                PdfDocument document = htmlConverter.Convert(strHTML, "");

                CreateOutputFolder();
                string outputPath = Path.Combine(DestinationPath, $"{Path.GetFileNameWithoutExtension(MSGFileName)}.pdf");
                fileStream = new FileStream(outputPath, FileMode.OpenOrCreate, FileAccess.ReadWrite);

                //Save and close the PDF document 
                document.Save(fileStream);
                document.Save(output);
                document.Close(true);

                isConverted = true;
                //Message = $"processed successfully!";
            }
            catch (Exception ex)
            {
                isConverted = false;
                string error = $"Exception Occured while coverting file at {SourceStream} to PDF , exception :  {ex.Message} , stacktrace : {ex.StackTrace}";
                Console.WriteLine(error);
                //Message = error;
            }
            finally
            {
                if (fileStream != null)
                    fileStream.Dispose();
            }
            return output;
        }


        private void CreateOutputFolder(string subpath = "")
        {
            string msgfilefolder = string.Concat(OutputFilePath, @"\msgattachments", !string.IsNullOrEmpty(subpath) ? @$"\{subpath}" : "");
            if (!Directory.Exists(msgfilefolder))
                Directory.CreateDirectory(msgfilefolder);
        }

    }
}
