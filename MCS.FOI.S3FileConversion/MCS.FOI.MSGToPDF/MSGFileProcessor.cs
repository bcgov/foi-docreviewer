using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading;
using System.Xml;
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

        public MSGFileProcessor() { }


        public MSGFileProcessor(Stream sourceStream)
        {
            this.SourceStream = sourceStream;

        }


        public (bool, string, Stream, Dictionary<MemoryStream, Dictionary<string, string>>) ConvertToPDF()
        {
            string message = $"No attachments to move to output folder";
            bool moved = true;
            string outputpath = string.Empty;
            MemoryStream output = new();
            Dictionary<MemoryStream, Dictionary<string, string>> attachmentsObj = new();
            try
            {
                Dictionary<string, Object> problematicFiles = null;

                if (SourceStream != null && SourceStream.Length > 0)
                {
                    for (int attempt = 1; attempt < FailureAttemptCount; attempt++)
                    {
                        try
                        {
                            using var msg = new MsgReader.Outlook.Storage.Message(SourceStream);
                            string htmlString = GenerateHtmlfromMsg(msg);
                            bool isConverted;
                            (output, isConverted) = ConvertHTMLtoPDF(htmlString, output);

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
                                    problematicFiles = problematicFiles == null ? new Dictionary<string, Object>() : problematicFiles;
                                    problematicFiles.Add(file.FileName, file);
                                }
                            }

                            if (problematicFiles != null)
                            {
                                int cnt = 0;
                                foreach (var attachmenttomove in problematicFiles)
                                {
                                    MemoryStream attachmentStream = new();
                                    //if (attachmenttomove.Key.ToLower().Contains(".msg"))
                                    //{
                                    //    var _attachment = (Storage.Message)attachmenttomove.Value;
                                    //    foreach (var subattachment in _attachment.Attachments)
                                    //    {
                                    //        var type = subattachment.GetType().FullName;
                                    //        if (type.ToLower().Contains("attachment"))
                                    //        {
                                    //            var file = (Storage.Attachment)subattachment;
                                    //            File.WriteAllBytes(file.FileName, file.Data);
                                    //            attachmentStream.Write(file.Data, 0, file.Data.Length);
                                    //            attachmentsObj.Add(attachmentStream, file.FileName);
                                    //        }
                                    //    }
                                    //}
                                    //else
                                    //{
                                    var _attachment = (Storage.Attachment)attachmenttomove.Value;
                                    //File.WriteAllBytes(_attachment.FileName, _attachment.Data);
                                    attachmentStream.Write(_attachment.Data, 0, _attachment.Data.Length);
                                    Dictionary<string, string> attachmentInfo = new Dictionary<string, string>();
                                    attachmentInfo.Add("filename", _attachment.FileName);
                                    attachmentInfo.Add("size", _attachment.Data.Length.ToString());
                                    attachmentInfo.Add("lastmodified", _attachment.LastModificationTime.ToString());
                                    attachmentInfo.Add("created", _attachment.CreationTime.ToString());
                                    attachmentsObj.Add(attachmentStream, attachmentInfo);
                                    //}
                                    cnt++;
                                }
                                moved = true;
                                message = string.Concat($"{cnt} problematic files moved", outputpath);
                            }

                            break;
                        }
                        catch (Exception e)
                        {
                            message = $"Exception happened while accessing File {SourceStream}, re-attempting count : {attempt} , Error Message : {e.Message} , Stack trace : {e.StackTrace}";
                            Log.Error(message);
                            Console.WriteLine(message);
                            if (attempt == FailureAttemptCount)
                            {
                                throw;
                            }
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
                throw;
            }

            return (moved, message, output, attachmentsObj);
        }


        private string GenerateHtmlfromMsg(Storage.Message msg)
        {
            try
            {
                var sb = new StringBuilder();
                StringBuilder htmlString = new();
                htmlString.Append(@"
                            <html>
                                <head>
                                </head>
                                <body style='border: 50px solid white;'>
                                    ");

                htmlString.Append(@"<div class='header style='padding:2% 0 2% 0; border-top:5px solid white; border-bottom: 5px solid white;'><table style='border: 5px; padding: 0; font-size:15px;'>");
                //Sender Name and Email
                string sender = string.Empty;
                if (msg.Sender != null && msg.Sender.DisplayName != null)
                {
                    sender = (msg.Sender.Email != null && msg.Sender.Email != "") ? msg.Sender.DisplayName + "(" + msg.Sender.Email + ")" : msg.Sender.DisplayName;
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
                string message = @"" + msg.BodyText.Replace("\n", "<br>").Replace("&lt;br&gt;", "<br>").Replace("&lt;br/&gt;", "<br/>");
                message = message.Replace("&lt;a", "<a").Replace("&lt;/a&gt;", "</a>");
                htmlString.Append(@"<tr><td><b>Message Body: </b></td></tr>
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
                throw;
            }
        }

        private (MemoryStream, bool) ConvertHTMLtoPDF(string strHTML, MemoryStream output)
        {
            bool isConverted;
            try
            {
                //Initialize HTML to PDF converter with Blink rendering engine
                HtmlToPdfConverter htmlConverter = new HtmlToPdfConverter(HtmlRenderingEngine.Blink);
                BlinkConverterSettings settings = new BlinkConverterSettings();
                settings.EnableHyperLink = false;
                //Set command line arguments to run without sandbox.
                settings.CommandLineArguments.Add("--no-sandbox");
                settings.CommandLineArguments.Add("--disable-setuid-sandbox");
                htmlConverter.ConverterSettings = settings;
                //Convert HTML string to PDF
                PdfDocument document = htmlConverter.Convert(strHTML, "");
                //Save and close the PDF document 
                document.Save(output);
                document.Close(true);
                isConverted = true;
            }
            catch (Exception ex)
            {
                isConverted = false;
                string error = $"Exception Occured while coverting file at {SourceStream} to PDF , exception :  {ex.Message} , stacktrace : {ex.StackTrace}";
                Console.WriteLine(error);
                throw;
            }

            return (output, isConverted);
        }

    }
}