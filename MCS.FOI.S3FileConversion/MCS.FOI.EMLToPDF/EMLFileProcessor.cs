using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Reflection.PortableExecutable;
using System.Text;
using System.Threading;
using MsgReader;
using MsgReader.Helpers;
using MsgReader.Outlook;
using RtfPipe.Tokens;
using Serilog;
using Syncfusion.HtmlConverter;
using Syncfusion.Pdf;
using Syncfusion.Pdf.Graphics;
using Syncfusion.Pdf.Interactive;
using static System.Net.WebRequestMethods;

namespace MCS.FOI.EMLToPDF
{
    public class EMLFileProcessor : IEMLFileProcessor
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



        public EMLFileProcessor() { }


        public EMLFileProcessor(Stream sourceStream, string destinationPath, string fileName)
        {
            this.DestinationPath = destinationPath;
            this.MSGFileName = fileName;
            this.SourceStream = sourceStream;

        }


        public (bool, string, string, Stream) ConvertToPDF()
        {
            var message = $"No attachments to move to output folder";
            bool moved = true;
            string outputpath = string.Empty;
            MemoryStream output = new MemoryStream();
            PdfDocument document = new PdfDocument();
            try
            {
                //string sourceFile = Path.Combine(MSGSourceFilePath, MSGFileName);
                Dictionary<string, Object> problematicFiles = null;

                
                    for (int attempt = 1; attempt < FailureAttemptCount; attempt++)
                    {
                        try
                        {
                        var msg = MsgReader.Mime.Message.Load(SourceStream);
                            string htmlString = generateHtmlfromEML(msg);
                        //(output, document) = ConvertHTMLtoPDF(htmlString, output);
                        PdfAttachmentCollection attachmentList = new PdfAttachmentCollection();
                        var attachments = msg.Attachments;
                            foreach (Object attachment in attachments)
                            {
                                var type = attachment.GetType().FullName;
                                if (type.ToLower().Contains("message"))
                                {
                                    var file = (MsgReader.Mime.MessagePart)attachment;
                                    problematicFiles = problematicFiles == null ? new Dictionary<string, Object>() : problematicFiles;
                                    problematicFiles.Add(file.FileName, file);

                                }
                                else
                                {
                                    var file = (Storage.Attachment)attachment;
                                    if (file.FileName.ToLower().Contains(".xls") || file.FileName.ToLower().Contains(".ics") || file.FileName.ToLower().Contains(".msg"))
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
                                        var _attachment = (MsgReader.Mime.MessagePart)attachmenttomove.Value;
                                        string fileName = @$"{OutputFilePath}\msgattachments\{Path.GetFileNameWithoutExtension(MSGFileName)}_{_attachment.FileName}";
                                    //foreach (var subattachment in _attachment)
                                    //{
                                    //    var type = subattachment.GetType().FullName;
                                    //    if (type.ToLower().Contains("attachment"))
                                    //    {
                                    //        var file = (Storage.Attachment)subattachment;
                                    //        CreateOutputFolder("subattachments");
                                    //        string _fileName = @$"{OutputFilePath}\msgattachments\subattachments\{Path.GetFileNameWithoutExtension(MSGFileName)}_{file.FileName}";
                                    //        File.WriteAllBytes(_fileName, file.Data);
                                    //    }
                                    //}
                                    CreateOutputFolder("subattachments");
                                    string _fileName = @$"{OutputFilePath}\msgattachments\subattachments\{Path.GetFileNameWithoutExtension(MSGFileName)}_{fileName}";
                                    FileInfo file = new FileInfo(fileName);
                                    //document.Attachments.Add(AddAttachment(file, _attachment.Body));
                                    attachmentList.Add(AddAttachment(file, _attachment.Body));
                                    }
                                    else
                                    {
                                        var _attachment = (MsgReader.Mime.MessagePart)attachmenttomove.Value;
                                        string fileName = @$"{OutputFilePath}\msgattachments\{Path.GetFileNameWithoutExtension(MSGFileName)}_{_attachment.FileName}";
                                        CreateOutputFolder();
                                        FileInfo file = new FileInfo(fileName);
                                        //document.Attachments.Add(AddAttachment(file, _attachment.Body));
                                        attachmentList.Add(AddAttachment(file, _attachment.Body));
                                        System.IO.File.WriteAllBytes(fileName, _attachment.Body);
                                        outputpath += fileName;
                                    }
                                    cnt++;
                                }
                                moved = true;
                                message = string.Concat($"{cnt} problematic files moved", outputpath);
                            }
                            (output, document) = ConvertHTMLtoPDF(htmlString, output, attachmentList);
                            break;
                        //}
                       
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
                throw;
            }

            return (moved, message, outputpath, output);
        }


        private PdfAttachment AddAttachment(FileInfo f, byte[] body)
        {
            PdfAttachment attachment = new PdfAttachment(f.FullName, body);
            attachment.ModificationDate = DateTime.Now;
            attachment.Description = f.Name;
            attachment.MimeType = "application/" + f.Extension;
            //Returns the attachment to the document
            return attachment;
        }

        private string generateHtmlfromEML(MsgReader.Mime.Message msg)
        {

            try
            {
                StringBuilder htmlString = new StringBuilder();
                htmlString.Append(@"
                            <html>
                                <head>
                                </head>
                                <body style='border: 50px solid white;'>
                                    ");

                htmlString.Append(@"<div class='header style='padding:2% 0 2% 0; border-top:5px solid white; border-bottom: 5px solid white;'><table style='border: 5px; padding: 0; font-size:20px;'>");
                
                string sender = string.Empty;
                var emailHeader = msg.Headers;
                if(emailHeader != null) {
                    //Sender Name and Email
                    if (emailHeader.From != null && emailHeader.From.DisplayName != null)
                    {
                        string displayName = emailHeader.From.DisplayName;
                        string senderEmail = emailHeader.From.Address;
                        sender = (senderEmail != null && senderEmail != "") ? displayName + "(" + senderEmail + ")" : displayName;
                    }
                    htmlString.Append(@"<tr>
                                <td><b>From: </b></td>
                                <td>" + sender + "</td></tr>");
                    //Recipient Name and Email
                    string recipientName = "";
                    foreach (var recipient in emailHeader.To)
                    {
                        recipientName += recipient.DisplayName +" (" + recipient.Address + ")";
                    }
                    string recipientCCName = "";
                    foreach (var recipientCC in emailHeader.Cc)
                    {
                        recipientCCName += recipientCC.DisplayName+" (" + recipientCC.Address + ")";
                    }
                    string recipientBccName = "";
                    foreach (var recipientBcc in emailHeader.Bcc)
                    {
                        recipientBccName += recipientBcc.DisplayName + " (" + recipientBcc.Address + ")";
                    }
                    
                    htmlString.Append(@"<tr>
                                <td><b>To: </b></td>
                                <td>" + recipientName + "</td></tr>");

                    if (!string.IsNullOrEmpty(recipientCCName))
                    {
                        htmlString.Append(@"<tr>
                                    <td><b>To: </b></td>
                                    <td>" + recipientCCName + "</td></tr>");
                    }

                    if (!string.IsNullOrEmpty(recipientBccName))
                    {
                        htmlString.Append(@"<tr>
                                <td><b>To: </b></td>
                                <td>" + recipientBccName + "</td></tr>");
                    }

                    htmlString.Append(@"<tr>
                                <td><b>Subject: </b></td>
                                <td>" + emailHeader.Subject + "</td></tr>");

                    //Message Sent On timestamp
                    htmlString.Append(@"<tr>
                                <td><b>Sent: </b></td>
                                <td>" + emailHeader.DateSent + "</td></tr>");

                    htmlString.Append(@"<tr>
                                <td><b>Priority: </b></td>
                                <td>" + emailHeader.Importance + "</td></tr>");
                }
                //Message body
                //string message = @"" + msg.BodyText.Replace("<", "&lt;").Replace(">", "&gt;").Replace("\n", "<br>");
                string message = "";
                if (!msg.MessagePart.IsMultiPart)
                {
                    message = @"" + msg.TextBody.GetBodyAsText().Replace("<", "&lt;").Replace(">", "&gt;").Replace("\n", "<br>");
                    message = message.Replace("&lt;br&gt;", "<br>").Replace("&lt;br/&gt;", "<br/>");
                    message = message.Replace("&lt;a", "<a").Replace("&lt;/a&gt;", "</a>");
                    htmlString.Append(@"<tr>
                                <td><b>Message Body: </b></td>
                                </tr>
                                <tr><td></td><td>" + message.Replace("&lt;br&gt;", "<br>").Replace("&lt;br/&gt;", "<br/>") + "</td></tr>");
                }
                else
                {
                    var body = msg.HtmlBody.GetBodyAsText();
                    message = @"" + body;
                    message = message.Replace("<html>","<br>").Replace("</html>", "<br>");
                    message = message.Replace("&lt;br&gt;", "<br>").Replace("&lt;br/&gt;", "<br/>");
                    message = message.Replace("&lt;a", "<a").Replace("&lt;/a&gt;", "</a>");
                    htmlString.Append(@"<tr>
                                <td><b>Message Body: </b></td>
                                </tr>
                                <tr><td></td><td>" + message.Replace("&lt;br&gt;", "<br>").Replace("&lt;br/&gt;", "<br/>") + "</td></tr>");
                }
                
                
                htmlString.Append(@"
                                    </table>
                                </div>");

                htmlString.Append(@"</body></html>");
                return htmlString.ToString();
            }
            catch (Exception ex)
            {
                string error = $"Exception Occured while coverting file at {SourceStream} to HTML , exception :  {ex.Message} , stacktrace : {ex.StackTrace}";
                Console.WriteLine(error);
                //Message = error;
                throw;
                return error;
            }
        }

        private (MemoryStream, PdfDocument) ConvertHTMLtoPDF(string strHTML, MemoryStream output, PdfAttachmentCollection attachmentList)
        {
            bool isConverted;
            FileStream fileStream = null;
            PdfDocument document = new PdfDocument();
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
                document = htmlConverter.Convert(strHTML, "");

                CreateOutputFolder();
                string outputPath = Path.Combine(DestinationPath, $"{Path.GetFileNameWithoutExtension(MSGFileName)}.pdf");
                fileStream = new FileStream(outputPath, FileMode.OpenOrCreate, FileAccess.ReadWrite);

                //Save and close the PDF document 
                document.Save(fileStream);
                for (int i = 0; i < attachmentList.Count; i++)
                {
                    document.Attachments.Add(attachmentList[i]);
                }
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
                throw;
                //Message = error;
            }
            finally
            {
                if (fileStream != null)
                    fileStream.Dispose();
            }
            return (output, document);
        }


        private void CreateOutputFolder(string subpath = "")
        {
            string msgfilefolder = string.Concat(OutputFilePath, @"\msgattachments", !string.IsNullOrEmpty(subpath) ? @$"\{subpath}" : "");
            if (!Directory.Exists(msgfilefolder))
                Directory.CreateDirectory(msgfilefolder);
        }

    }
}
