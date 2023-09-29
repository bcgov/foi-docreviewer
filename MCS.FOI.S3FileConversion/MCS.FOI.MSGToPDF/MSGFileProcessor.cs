using MsgReader.Outlook;
using MsgReader;
using Serilog;
using Syncfusion.HtmlConverter;
using Syncfusion.Pdf;
using Syncfusion.DocIO.DLS;
using Syncfusion.DocIORenderer;
using System.Net;
using System.Text;
using System.Text.RegularExpressions;
using Syncfusion.DocIO;
using System.Collections.Generic;
using Syncfusion.Pdf.HtmlToPdf;
using System.ComponentModel.DataAnnotations;
using System;

namespace MCS.FOI.MSGToPDF
{
    public class MSGFileProcessor : IMSGFileProcessor, IDisposable
    {
        public Stream SourceStream { get; set; }
        public bool IsSinglePDFOutput { get; set; }
        public int FailureAttemptCount { get; set; }
        public int WaitTimeinMilliSeconds { get; set; }

        Dictionary<MemoryStream, Dictionary<string, string>> attachmentsObj = null;

        private MemoryStream? output = null;
        private MemoryStream? attachmentStream = null;
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
            output = new();
            attachmentsObj = new();
            try
            {
                if (SourceStream != null && SourceStream.Length > 0)
                {
                    for (int attempt = 1; attempt <= FailureAttemptCount; attempt++)
                    {
                        try
                        {
                            using var msg = new MsgReader.Outlook.Storage.Message(SourceStream);
                            Dictionary<string, Boolean> fileNameHash = new();
                            foreach (Object attachment in msg.Attachments)
                            {
                                attachmentStream = new();
                                if (attachment.GetType().FullName.ToLower().Contains("message"))
                                {
                                    var _attachment = (Storage.Message)attachment;
                                    var filename = _attachment.FileName;
                                    var extension = Path.GetExtension(filename);
                                    if (!string.IsNullOrEmpty(extension))
                                    {
                                        _attachment.Save(attachmentStream);
                                        Dictionary<string, string> attachmentInfo = new Dictionary<string, string>();

                                        if (fileNameHash.ContainsKey(filename))
                                        {

                                            filename = Path.GetFileNameWithoutExtension(filename) + '1' + extension;
                                        }
                                        fileNameHash.Add(filename, true);
                                        attachmentInfo.Add("filename", _attachment.FileName);
                                        attachmentInfo.Add("s3filename", filename);
                                        attachmentInfo.Add("size", attachmentStream.Capacity.ToString());
                                        attachmentInfo.Add("lastmodified", _attachment.LastModificationTime.ToString());
                                        attachmentInfo.Add("created", _attachment.CreationTime.ToString());
                                        attachmentsObj.Add(attachmentStream, attachmentInfo);
                                    }
                                }
                                else
                                {
                                    var _attachment = (Storage.Attachment)attachment;
                                    var filename = _attachment.FileName;
                                    var extension = Path.GetExtension(filename);

                                    if (!string.IsNullOrEmpty(extension))
                                    {
                                        attachmentStream.Write(_attachment.Data, 0, _attachment.Data.Length);
                                        Dictionary<string, string> attachmentInfo = new Dictionary<string, string>();

                                        if (fileNameHash.ContainsKey(filename))
                                        {

                                            filename = Path.GetFileNameWithoutExtension(filename) + '1' + extension;
                                        }
                                        Console.WriteLine("attachmentname: " + _attachment.FileName);
                                        Console.WriteLine("attachmentpos: " + _attachment.RenderingPosition);
                                        Console.WriteLine("attachmentmime: " + extension);
                                        Console.WriteLine("attachmentsize: " + _attachment.Data.Length.ToString());
                                        fileNameHash.Add(filename, true);
                                        attachmentInfo.Add("filename", _attachment.FileName);
                                        attachmentInfo.Add("s3filename", filename);
                                        attachmentInfo.Add("cid", _attachment.ContentId);
                                        attachmentInfo.Add("size", _attachment.Data.Length.ToString());
                                        attachmentInfo.Add("lastmodified", _attachment.LastModificationTime.ToString());
                                        attachmentInfo.Add("created", _attachment.CreationTime.ToString());
                                        attachmentsObj.Add(attachmentStream, attachmentInfo);
                                    }
                                }
                            }
                            if (msg.BodyRtf != null)
                            {
                                var msgReader = new Reader();

                                var inputStream = new MemoryStream();
                                string body = msgReader.ExtractMsgEmailBody(SourceStream, ReaderHyperLinks.Both, "text/html; charset=utf-8", false);
                                var bodyreplaced = Regex.Replace(Regex.Replace(body.Replace("<br>", "<br/>").Replace("<![if !supportAnnotations]>", "").Replace("<![endif]>", ""), "=(?<tagname>(?!utf-8)[\\w|-]+)", "=\"${tagname}\""), "<meta .*?>", "");
                                const string rtfInlineObject = "[*[RTFINLINEOBJECT]*]";
                                const string imgString = "<img";
                                bool htmlInline = bodyreplaced.Contains(imgString);
                                bool rtfInline = bodyreplaced.Contains(rtfInlineObject);
                                if (htmlInline || rtfInline)
                                {
                                    var inlineAttachments = new List<Storage.Attachment>();
                                    foreach (Object attachment in msg.Attachments)
                                    {
                                        if (!attachment.GetType().FullName.ToLower().Contains("message"))
                                        {
                                            var _attachment = (Storage.Attachment)attachment;
                                            if (htmlInline)
                                            {
                                                if (!String.IsNullOrEmpty(_attachment.ContentId) && bodyreplaced.Contains(_attachment.ContentId))
                                                {
                                                    inlineAttachments.Add(_attachment);
                                                }
                                            }
                                            else if (rtfInline)
                                            {
                                                inlineAttachments.Add(_attachment);
                                            }
                                        }
                                    }
                                    foreach (var inlineAttachment in inlineAttachments.OrderBy(m => m.RenderingPosition))
                                    {
                                        if (htmlInline)
                                        {
                                            var match = Regex.Match(bodyreplaced, "<img.*cid:" + inlineAttachment.ContentId + ".*?>");
                                            var width = float.Parse(Regex.Match(match.Value, "(?<=width=\")\\d+").Value);
                                            var height = float.Parse(Regex.Match(match.Value, "(?<=height=\")\\d+").Value);
                                            const float maxSize = 750;
                                            if (width > maxSize)
                                            {
                                                float scale = maxSize / width;
                                                width = maxSize;
                                                height = scale * height;
                                            }
                                            else if (height > maxSize)
                                            {
                                                float scale = maxSize / height;
                                                height = maxSize;
                                                width = scale * width;
                                            }
                                            bodyreplaced = Regex.Replace(bodyreplaced, "<img.*cid:" + inlineAttachment.ContentId + ".*?>", "<img width='" + width.ToString() + "' height ='" + height.ToString() + "' src=\"data:" + inlineAttachment.MimeType + ";base64," + Convert.ToBase64String(inlineAttachment.Data) + "\"/>");
                                            foreach (KeyValuePair<MemoryStream, Dictionary<string, string>> attachment in attachmentsObj)
                                            {
                                                if (attachment.Value["cid"] == inlineAttachment.ContentId)
                                                {
                                                    attachmentsObj.Remove(attachment.Key);
                                                }
                                            }
                                        }
                                        else if (rtfInline)
                                        {
                                            if (inlineAttachment.OleAttachment)
                                            {
                                                bodyreplaced = ReplaceFirstOccurrence(bodyreplaced, rtfInlineObject, "<img src=\"data:image/" + Path.GetExtension(inlineAttachment.FileName) + ";base64," + Convert.ToBase64String(inlineAttachment.Data) + "\"/>");
                                                foreach (KeyValuePair<MemoryStream, Dictionary<string, string>> attachment in attachmentsObj)
                                                {
                                                    if (attachment.Value["filename"] == inlineAttachment.FileName)
                                                    {
                                                        attachmentsObj.Remove(attachment.Key);
                                                    }
                                                }
                                            }
                                            else
                                            {
                                                bodyreplaced = ReplaceFirstOccurrence(bodyreplaced, rtfInlineObject, " <b>[**Inline Attachment - " + inlineAttachment.FileName + "**]</b>");
                                            }
                                        }
                                    }                                    
                                }

                                
                                byte[] byteArray = Encoding.ASCII.GetBytes(bodyreplaced);
                                using (MemoryStream messageStream = new MemoryStream(byteArray))
                                {
                                    //messageStream.WriteTo(fs4);
                                    using (WordDocument rtfDoc = new WordDocument(messageStream, Syncfusion.DocIO.FormatType.Html))
                                    {
                                        //rtfDoc.Save(fs3, FormatType.Docx);
                                        // Replace leading tabs, issue with syncfusion
                                        rtfDoc.ReplaceFirst = true;
                                        var regex = new Regex(@"(\r)*(\n)*(\t)+", RegexOptions.Multiline);
                                        var occurences = rtfDoc.Replace(regex, "\r\n");

                                        List<Entity> pictures = rtfDoc.FindAllItemsByProperty(EntityType.Picture, "", "");

                                        foreach (WPicture picture in pictures)
                                        {
                                            picture.LockAspectRatio = true;
                                            const float maxSize = 500;
                                            if (picture.Height > maxSize && picture.Height >= picture.Width)
                                            {
                                                var scale = (maxSize / picture.Height) * 100;
                                                picture.HeightScale = scale;
                                                picture.WidthScale = scale;
                                            }
                                            if (picture.Width > maxSize)
                                            {
                                                var scale = (maxSize / picture.Width) * 100;
                                                picture.HeightScale = scale;
                                                picture.WidthScale = scale;
                                            }
                                        }

                                        //Gets all the hyperlink fields in the document

                                        List<Entity> fields = rtfDoc.FindAllItemsByProperty(EntityType.Field, "FieldType", FieldType.FieldHyperlink.ToString());

                                        if (fields != null)
                                        {
                                            for (int i = 0; i < fields.Count; i++)

                                            {

                                                //Creates hyperlink instance from field to manipulate the hyperlink.

                                                Hyperlink hyperlink = new Hyperlink(fields[i] as WField);

                                                //Gets the text to display from hyperlink

                                                string existingHyperlinkText = hyperlink.TextToDisplay;

                                                //Removes the content between tags

                                                if (!string.IsNullOrEmpty(existingHyperlinkText))
                                                {
                                                    string modifiedTextToDisplay = RemoveContentBetweenTags(existingHyperlinkText);

                                                    //Sets the modified text to display to hyperlink

                                                    hyperlink.TextToDisplay = modifiedTextToDisplay;
                                                }

                                            }
                                        }


                                        WordDocument doc = GetEmailMetatdata(msg);


                                        //Sets the break-code of First section of source document as NoBreak to avoid imported from a new page

                                        rtfDoc.Sections[0].BreakCode = SectionBreakCode.NoBreak;

                                        //Gets the destination document page properties.

                                        WPageSetup destSecPageSetup = doc.LastSection.PageSetup;

                                        //Processes each section in the source Word document.

                                        for (int i = 0; i < rtfDoc.Sections.Count; i++)

                                        {

                                            WSection sourceSection = rtfDoc.Sections[i];

                                            //Sets the destination document page setup properties to the source document sections.

                                            sourceSection.PageSetup.DifferentFirstPage = destSecPageSetup.DifferentFirstPage;

                                            sourceSection.PageSetup.Margins = destSecPageSetup.Margins;

                                            sourceSection.PageSetup.Orientation = destSecPageSetup.Orientation;

                                            sourceSection.PageSetup.PageSize = destSecPageSetup.PageSize;

                                        }

                                        doc.ImportContent(rtfDoc, ImportOptions.UseDestinationStyles);

                                        using (DocIORenderer renderer = new DocIORenderer())
                                        {
                                            using PdfDocument pdfDocument = renderer.ConvertToPDF(doc);
                                            //Save the PDF file
                                            //Close the instance of document objects
                                            pdfDocument.Save(output);
                                            pdfDocument.Close(true);

                                        }

                                    }
                                }
                            }
                            else
                            {
                                WordDocument doc = GetEmailMetatdata(msg);
                                doc.LastParagraph.AppendText("This email does not have a message body.");

                                using (DocIORenderer renderer = new DocIORenderer())
                                {
                                    using PdfDocument pdfDocument = renderer.ConvertToPDF(doc);
                                    //Save the PDF file
                                    //Close the instance of document objects
                                    pdfDocument.Save(output);
                                    pdfDocument.Close(true);

                                }
                            }



                            //string htmlString = GenerateHtmlfromMsg(msg);
                            //bool isConverted;
                            //(output, isConverted) = ConvertHTMLtoPDF(htmlString, output);

                            


                            break;
                        }
                        catch (Exception e)
                        {
                            string errorMessage = $"Exception occured while coverting a message file, exception :  {e.Message}";
                            message = $"Exception happened while accessing the File, re-attempting count : {attempt} , Error Message : {e.Message} , Stack trace : {e.StackTrace}";
                            Log.Error(message);
                            Console.WriteLine(message);
                            if (attempt == FailureAttemptCount)
                            {
                                throw new Exception(errorMessage);
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

                htmlString.Append(@"<div class='header style='padding:2% 0 2% 0; border-top:5px solid white; border-bottom: 5px solid white;'><table style='border: 5px; padding: 0; font-size:35px;'>");
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

                //Message Attachments
                string attachmentsList = "";
                foreach (Object attachment in msg.Attachments)
                {
                    if (attachment.GetType().FullName.ToLower().Contains("message"))
                    {
                        var _attachment = (Storage.Message)attachment;
                        attachmentsList += (_attachment.FileName + ", ");
                    }
                    else
                    {
                        var _attachment = (Storage.Attachment)attachment;
                        attachmentsList += _attachment.FileName + ", ";
                    }

                }
                if (!string.IsNullOrEmpty(attachmentsList))
                {

                    htmlString.Append(@"<tr>
                            <td><b>Attachments: </b></td>
                            <td>" + attachmentsList.Remove(attachmentsList.Length - 2, 2) + "</td></tr>");
                }

                //Message body
                string message = @"" + msg.BodyText?.Replace("\n", "<span style='display: block;margin-bottom: 1em;'></span>").Replace("&lt;br&gt;", "<span style='display: block;margin-bottom: 1em;'></span>")?.Replace("&lt;br/&gt;", "<span style='display: block;margin-bottom: 1em;'></span>");

                message = message.Replace("&lt;a", "<a").Replace("&lt;/a&gt;", "</a>");
                htmlString.Append(@"<tr><td><b>Message Body: </b></td></tr>
                                    <tr><td></td><td>" + message.Replace("&lt;br&gt;", "<span style='display: block;margin-bottom: 1em;'></span>").Replace("&lt;br/&gt;", "<span style='display: block;margin-bottom: 1em;'></span>") + "</td></tr>");
                htmlString.Append(@"
                                    </table>
                                </div>");
                htmlString.Append(@"</body></html>");
                return htmlString.ToString();
            }
            catch (Exception ex)
            {
                string error = $"Exception Occured while coverting file to HTML , exception :  {ex.Message} , stacktrace : {ex.StackTrace}";
                Console.WriteLine(error);
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
                settings.EnableHyperLink = true;
                settings.SinglePageLayout = SinglePageLayout.FitHeight;
                //Set command line arguments to run without sandbox.
                settings.CommandLineArguments.Add("--no-sandbox");
                settings.CommandLineArguments.Add("--disable-setuid-sandbox");
                settings.Scale = 1.0F;
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
                string error = $"Exception Occured while coverting file to PDF , exception :  {ex.Message} , stacktrace : {ex.StackTrace}";
                Console.WriteLine(error);
                throw;
            }

            return (output, isConverted);
        }

        public void Dispose()
        {
            Dispose(true);
            GC.SuppressFinalize(this);
        }

        protected WordDocument GetEmailMetatdata(MsgReader.Outlook.Storage.Message msg)
        {
            WordDocument doc = new WordDocument();
            IWSection section = doc.AddSection();
            IWParagraph paragraph = section.AddParagraph();
            paragraph.AppendText("From: ").CharacterFormat.Bold = true;
            var sender = "";
            if (msg.Sender != null && msg.Sender.DisplayName != null)
            {
                sender = (msg.Sender.Email != null && msg.Sender.Email != "") ? msg.Sender.DisplayName + " (" + msg.Sender.Email + ")" : msg.Sender.DisplayName;
            }
            paragraph.AppendText(sender).CharacterFormat.Bold = false;
            paragraph.AppendBreak(BreakType.LineBreak);
            string recipientName = "";
            foreach (var recipient in msg.GetEmailRecipients(RecipientType.To, false, false))
            {
                recipientName += recipient;
            }

            if (!string.IsNullOrEmpty(recipientName))
            {
                paragraph.AppendText("To: ").CharacterFormat.Bold = true;
                paragraph.AppendText(recipientName.Replace("<", "(").Replace(">", ")")).CharacterFormat.Bold = false;
                paragraph.AppendBreak(BreakType.LineBreak);
            }
            string recipientCCName = "";
            foreach (var recipient in msg.GetEmailRecipients(RecipientType.Cc, false, false))
            {
                recipientCCName += recipient;
            }
            if (!string.IsNullOrEmpty(recipientCCName))
            {
                paragraph.AppendText("Cc: ").CharacterFormat.Bold = true;
                paragraph.AppendText(recipientCCName.Replace("<", "(").Replace(">", ")")).CharacterFormat.Bold = false;
                paragraph.AppendBreak(BreakType.LineBreak);
            }
            string recipientBCCName = "";
            foreach (var recipient in msg.GetEmailRecipients(RecipientType.Bcc, false, false))
            {
                recipientBCCName += recipient;
            }
            if (!string.IsNullOrEmpty(recipientBCCName))
            {
                paragraph.AppendText("Bcc: ").CharacterFormat.Bold = true;
                paragraph.AppendText(recipientBCCName.Replace("<", "(").Replace(">", ")")).CharacterFormat.Bold = false;
                paragraph.AppendBreak(BreakType.LineBreak);
            }

            paragraph.AppendText("Subject: ").CharacterFormat.Bold = true;
            paragraph.AppendText(msg.Subject).CharacterFormat.Bold = false;
            paragraph.AppendBreak(BreakType.LineBreak);

            paragraph.AppendText("Sent: ").CharacterFormat.Bold = true;
            paragraph.AppendText("" + msg.SentOn).CharacterFormat.Bold = false;
            paragraph.AppendBreak(BreakType.LineBreak);


            string attachmentsList = "";
            foreach (Object attachment in msg.Attachments)
            {
                if (attachment.GetType().FullName.ToLower().Contains("message"))
                {
                    var _attachment = (Storage.Message)attachment;
                    attachmentsList += (_attachment.FileName + ", ");
                }
                else
                {
                    var _attachment = (Storage.Attachment)attachment;
                    attachmentsList += _attachment.FileName + ", ";
                }

            }


            if (!string.IsNullOrEmpty(attachmentsList))
            {
                paragraph.AppendText("Attachments: ").CharacterFormat.Bold = true;
                paragraph.AppendText(attachmentsList.Remove(attachmentsList.Length - 2, 2)).CharacterFormat.Bold = false;
                paragraph.AppendBreak(BreakType.LineBreak);
            }


            paragraph.AppendText("Message Body: ").CharacterFormat.Bold = true;
            paragraph.AppendBreak(BreakType.LineBreak);

            return doc;
        }

        private static string ReplaceFirstOccurrence(string text, string search, string replace)
        {
            var index = text.IndexOf(search, StringComparison.Ordinal);
            if (index < 0)
                return text;

            return text.Substring(0, index) + replace + text.Substring(index + search.Length);
        }

        protected virtual void Dispose(bool disposing)
        {
            if (disposing)
            {
                if (this.SourceStream != null)
                {
                    this.SourceStream.Close();
                    this.SourceStream.Dispose();
                }

                if (output != null) output.Dispose();
                if (attachmentStream != null) attachmentStream.Dispose();
                if (attachmentsObj != null) attachmentsObj = null;
                // free managed resources
            }

        }

        /// <summary>

        /// Remove the content between tags

        /// </summary>

        /// <param name="inputString">Input string</param>

        /// <returns>Remove the content between '<' and  '>' And returns the remaining string</returns>

        static string RemoveContentBetweenTags(string inputString)

        {

            string result = "";

            bool insideTag = false;

            foreach (char c in inputString)

            {

                if (c == '<')

                {

                    insideTag = true;

                    continue;

                }

                else if (c == '>')

                {

                    insideTag = false;

                    continue;

                }

                if (!insideTag)

                {

                    result += c;

                }

            }



            return result;

        }

    }
}
