using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
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

namespace MCS.FOI.MSGToPDF
{
    public class MSGFileProcessor : IMSGFileProcessor
    {
        public Stream SourceStream { get; set; }
        public bool IsSinglePDFOutput { get; set; }
        public int FailureAttemptCount { get; set; }
        public int WaitTimeinMilliSeconds { get; set; }
        public string HTMLtoPdfWebkitPath { get; set; }



        public MSGFileProcessor() { }


        public MSGFileProcessor(Stream sourceStream)
        {
            this.SourceStream = sourceStream;

        }


        public (bool, string, Stream, Dictionary<MemoryStream, string>) ConvertToPDF()
        {
            var message = $"No attachments to move to output folder";
            bool moved = true;
            string outputpath = string.Empty;
            MemoryStream output = new MemoryStream();
            MemoryStream attachmentStream = new MemoryStream();
            Dictionary<MemoryStream, string> attachmentsObj = new Dictionary<MemoryStream, string>();
            try
            {
                Dictionary<string, Object> problematicFiles = null;

                if (SourceStream != null && SourceStream.Length > 0)
                {
                    for (int attempt = 1; attempt < FailureAttemptCount; attempt++)
                    {
                        try
                        {
                            using (var msg = new MsgReader.Outlook.Storage.Message(SourceStream))
                            {
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
                                        if (file.FileName.ToLower().Contains(".xls") || file.FileName.ToLower().Contains(".xlsx") || file.FileName.ToLower().Contains(".ics") || 
                                            file.FileName.ToLower().Contains(".msg") || file.FileName.ToLower().Contains(".doc") || file.FileName.ToLower().Contains(".docx"))
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
                                        attachmentStream = new MemoryStream();
                                        if (attachmenttomove.Key.ToLower().Contains(".msg"))
                                        {
                                            var _attachment = (Storage.Message)attachmenttomove.Value;
                                            foreach (var subattachment in _attachment.Attachments)
                                            {
                                                var type = subattachment.GetType().FullName;
                                                if (type.ToLower().Contains("attachment"))
                                                {
                                                    var file = (Storage.Attachment)subattachment;
                                                    File.WriteAllBytes(file.FileName, file.Data);
                                                    attachmentStream.Write(file.Data, 0, file.Data.Length);
                                                    attachmentsObj.Add(attachmentStream, file.FileName);
                                                }
                                            }
                                        }
                                        else
                                        {
                                            var _attachment = (Storage.Attachment)attachmenttomove.Value;
                                            File.WriteAllBytes(_attachment.FileName, _attachment.Data);
                                            attachmentStream.Write(_attachment.Data, 0, _attachment.Data.Length);
                                            attachmentsObj.Add(attachmentStream, _attachment.FileName);
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
                }
                else
                {
                    message = $"SourceStream does not exist!";
                    Log.Error(message);
                }
            }
            catch (Exception ex)
            {
                Log.Error($"Error happened while moving attachments on MSG File, Exception message : {ex.Message} , details : {ex.StackTrace}");
                message = $"Error happened while moving attachments on MSG File, Exception message : {ex.Message} , details : {ex.StackTrace}";
                moved = false;
            }

            return (moved, message, output, attachmentsObj);
        }


        private string generateHtmlfromMsg(Storage.Message msg)
        {
            try {
                var sb = new StringBuilder();
                StringBuilder htmlString = new StringBuilder();
                htmlString.Append(@"
                            <html>
                                <head>
                                </head>
                                <body style='border: 50px solid white;'>
                                    ");

                htmlString.Append(@"<div class='header style='padding:2% 0 2% 0; border-top:5px solid white; border-bottom: 5px solid white;'><table style='border: 5px; padding: 0; font-size:20px;'>");
                //Sender Name and Email
                string sender = string.Empty;
                if (msg.Sender != null && msg.Sender.DisplayName != null)
                {
                    sender = (msg.Sender.Email != null && msg.Sender.Email != "") ? msg.Sender.DisplayName + "(" + msg.Sender.Email + ")": msg.Sender.DisplayName;
                }
                htmlString.Append(@"<tr>
                            <td><b>From: </b></td>
                            <td>" + sender + "</td></tr>");
                //Recipient Name and Email
                string recipientName = "";
                foreach (var recipient in msg.GetEmailRecipients(RecipientType.To, false, false))
                {
                    recipientName += recipient;
                }
                string recipientCCName = "";
                foreach (var recipient in msg.GetEmailRecipients(RecipientType.Cc, false, false))
                {
                    recipientCCName += recipient;
                }
                string recipientBccName = "";
                foreach (var recipient in msg.GetEmailRecipients(RecipientType.Bcc, false, false))
                {
                    recipientBccName += recipient;
                }
                if (!string.IsNullOrEmpty(recipientName))
                {
                    htmlString.Append(@"<tr>
                            <td><b>To: </b></td>
                            <td>" + recipientName.Replace("<", "(").Replace(">", ")") + "</td></tr>");
                }

                if (!string.IsNullOrEmpty(recipientCCName))
                {
                    //recipientCCName = recipientCCName.Substring(1);
                    htmlString.Append(@"<tr>
                                <td><b>To: </b></td>
                                <td>" + recipientCCName.Replace("<", "(").Replace(">", ")") + "</td></tr>");
                }

                if (!string.IsNullOrEmpty(recipientBccName))
                {
                    //recipientBccName = recipientBccName.Substring(1);
                    htmlString.Append(@"<tr>
                            <td><b>To: </b></td>
                            <td>" + recipientBccName.Replace("<", "(").Replace(">", ")") + "</td></tr>");
                }

                htmlString.Append(@"<tr>
                            <td><b>Subject: </b></td>
                            <td>" + msg.Subject + "</td></tr>");

                //Message Sent On timestamp
                htmlString.Append(@"<tr>
                            <td><b>Sent: </b></td>
                            <td>" + msg.SentOn + "</td></tr>");

                //Message body
                string message = @"" + msg.BodyText.Replace("<", "&lt;").Replace(">", "&gt;").Replace("\n", "<br>");
                message = message.Replace("&lt;br&gt;", "<br>").Replace("&lt;br/&gt;", "<br/>");
                message = message.Replace("&lt;a", "<a").Replace("&lt;/a&gt;", "</a>");
                htmlString.Append(@"<tr>
                            <td><b>Message Body: </b></td>
                            </tr>
                            <tr><td></td><td>" + message.Replace("&lt;br&gt;", "<br>").Replace("&lt;br/&gt;", "<br/>") + "</td></tr>");
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
                return error;
            }
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
                //Save and close the PDF document 
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

    }
}
