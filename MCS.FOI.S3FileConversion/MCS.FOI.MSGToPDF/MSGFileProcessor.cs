using MsgReader.Outlook;
using MsgReader;
using SerilogNS = Serilog;
using Syncfusion.HtmlConverter;
using Syncfusion.Pdf;
using System.Text;
using System.Text.RegularExpressions;
using System.Linq;
using static MsgReader.Outlook.Storage;

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
                            string htmlString = GenerateHtmlfromMsg(msg);
                            Dictionary<string, Boolean> fileNameHash = new();
                            foreach (Object attachment in msg.Attachments)
                            {
                                attachmentStream = new();
                                if (attachment.GetType().FullName.ToLower().Contains("message"))
                                {
                                    var _attachment = (Storage.Message)attachment;
                                    var filename = _attachment.FileName;
                                    var extension = Path.GetExtension(filename);
                                    var baseFilename = Path.GetFileNameWithoutExtension(filename);
                                    if (!string.IsNullOrEmpty(extension))
                                    {
                                        _attachment.Save(attachmentStream);
                                        Dictionary<string, string> attachmentInfo = new Dictionary<string, string>();
                                        
                                        // If the filename already exists, increment the duplicate count to create a unique filename
                                        if (fileNameHash.ContainsKey(filename))
                                        {
                                            int duplicateCount = 1; // Initialize the duplicate count
                                            string newFilename;
                                            
                                            // Loop until a unique filename is found
                                            do
                                            {
                                                newFilename = baseFilename + duplicateCount.ToString() + extension;
                                                duplicateCount++;
                                            } while (fileNameHash.ContainsKey(newFilename));
                                            filename = newFilename;
                                        }
                                        fileNameHash.Add(filename, true);

                                        var lastModified = _attachment.LastModificationTime.ToString();
                                        var sentOn = _attachment.SentOn.ToString();
                                        if (!string.IsNullOrEmpty(sentOn))
                                            lastModified = sentOn;
                                            
                                        var attachmentSize = attachmentStream.Length.ToString();
                                        if (string.IsNullOrEmpty(attachmentSize))
                                            attachmentSize = attachmentStream.Capacity.ToString();

                                        attachmentInfo.Add("filename", _attachment.FileName);
                                        attachmentInfo.Add("s3filename", filename);
                                        attachmentInfo.Add("size", attachmentSize);
                                        attachmentInfo.Add("lastmodified", lastModified);
                                        attachmentInfo.Add("created", _attachment.CreationTime.ToString());
                                        attachmentsObj.Add(attachmentStream, attachmentInfo);
                                    }
                                }
                                else
                                {
                                    var _attachment = (Storage.Attachment)attachment;
                                    var filename = _attachment.FileName;
                                    var extension = Path.GetExtension(filename);
                                    var baseFilename = Path.GetFileNameWithoutExtension(filename);
                                    if (!string.IsNullOrEmpty(extension))
                                    {
                                        attachmentStream.Write(_attachment.Data, 0, _attachment.Data.Length);
                                        Dictionary<string, string> attachmentInfo = new Dictionary<string, string>();
                                        
                                        // If the filename already exists, increment the duplicate count to create a unique filename
                                        if (fileNameHash.ContainsKey(filename))
                                        {
                                            int duplicateCount = 1;  // Initialize the duplicate count
                                            string newFilename;
                                            // Loop until a unique filename is found
                                            do
                                            {
                                                newFilename = baseFilename + '-' +duplicateCount.ToString() + extension;
                                                duplicateCount++;
                                            } while (fileNameHash.ContainsKey(newFilename));
                                            filename = newFilename; // Set the unique filename
                                        }
                                        fileNameHash.Add(filename, true);
                                        attachmentInfo.Add("filename", filename);
                                        attachmentInfo.Add("s3filename", filename);
                                        attachmentInfo.Add("cid", _attachment.ContentId);
                                        attachmentInfo.Add("size", _attachment.Data.Length.ToString());
                                        attachmentInfo.Add("lastmodified", _attachment.LastModificationTime.ToString());
                                        attachmentInfo.Add("created", _attachment.CreationTime.ToString());
                                        attachmentsObj.Add(attachmentStream, attachmentInfo);
                                    }
                                }
                            }
                            ////WordDocument doc = GetEmailMetatdata(msg);

                            var msgReader = new Reader();
                            string body = msgReader.ExtractMsgEmailBody(SourceStream, ReaderHyperLinks.None, "text/html; charset=utf-8", false);
                            var options = RegexOptions.None;
                            var timeout = TimeSpan.FromSeconds(10);
                            var bodyreplaced = Regex.Replace(body, "page:WordSection1;", "", options, timeout);
                            bodyreplaced = Regex.Replace(bodyreplaced, "</style>", "table {max-width: 800px !important;}</style>", options, timeout);
                            //var bodyreplaced = Regex.Replace(Regex.Replace(Regex.Replace(Regex.Replace(Regex.Replace(Regex.Replace(Regex.Replace(body, "<br.*?>", "<br/>", options, timeout), "<hr.*?>", "<hr/>", options, timeout), "href=\"[^\"]*=[^\"]\"", "", options, timeout).Replace(";=\"\"", "").Replace("<![if !supportAnnotations]>", "").Replace("<![endif]>", ""), "=(?<tagname>(?!utf-8)[\\w|-]+)", "=\"${tagname}\"", options, timeout), "<meta .*?>", "", options, timeout), "<link.*?>", "", options, timeout), "<img src=\"(?!cid).*?>", "", options, timeout);
                            const string rtfInlineObject = "[*[RTFINLINEOBJECT]*]";
                            const string imgString = "<img(.|\\n)*src=\"cid(.|\\n)*?>";
                            bool htmlInline = Regex.Match(bodyreplaced, imgString).Success;
                            bool rtfInline = bodyreplaced.Contains(rtfInlineObject);
                            if (htmlInline || rtfInline)
                            {
                                var inlineAttachments = new List<object>();
                                foreach (Object attachment in msg.Attachments)
                                {
                                    if (!attachment.GetType().FullName.ToLower().Contains("message"))
                                    {
                                        var _attachment = (Storage.Attachment)attachment;
                                        if (htmlInline)
                                        {
                                            if (!String.IsNullOrEmpty(_attachment.ContentId) && (bodyreplaced.Contains(_attachment.ContentId) || _attachment.Hidden))
                                            {
                                                inlineAttachments.Add(_attachment);
                                            }
                                        }
                                        else if (rtfInline)
                                        {
                                            inlineAttachments.Add(_attachment);
                                        }
                                    }
                                    else if (rtfInline)
                                    {
                                        var _attachment = (Storage.Message)attachment;
                                        inlineAttachments.Add(_attachment);
                                    }
                                }
                                var startAt = 0;
                                foreach (var inlineAttachment in inlineAttachments.OrderBy(m => m.GetType().GetProperty("RenderingPosition").GetValue(m, null)))
                                {
                                    if (rtfInline)
                                    {
                                        if (!inlineAttachment.GetType().FullName.ToLower().Contains("message"))
                                        {
                                            var _inlineAttachment = (Storage.Attachment)inlineAttachment;
                                            if (_inlineAttachment.OleAttachment)
                                            {
                                                bodyreplaced = ReplaceFirstOccurrence(bodyreplaced, rtfInlineObject, "<img style=\"max-width: 700px\" src=\"data:image/" + Path.GetExtension(_inlineAttachment.FileName) + ";base64," + Convert.ToBase64String(_inlineAttachment.Data) + "\"/>");
                                                foreach (KeyValuePair<MemoryStream, Dictionary<string, string>> attachment in attachmentsObj)
                                                {
                                                    if (attachment.Value["filename"] == _inlineAttachment.FileName)
                                                    {
                                                        attachmentsObj.Remove(attachment.Key);
                                                    }
                                                }
                                            }
                                            else
                                            {
                                                bodyreplaced = ReplaceFirstOccurrence(bodyreplaced, rtfInlineObject, " <b>[**Inline Attachment - " + _inlineAttachment.FileName + "**]</b>");
                                            }
                                        }
                                        else
                                        {
                                            var _inlineAttachment = (Storage.Message)inlineAttachment;
                                            bodyreplaced = ReplaceFirstOccurrence(bodyreplaced, rtfInlineObject, " <b>[**Inline Attachment - " + _inlineAttachment.FileName + "**]</b>");
                                        }
                                    }
                                    else if (htmlInline)
                                    {
                                        var _inlineAttachment = (Storage.Attachment)inlineAttachment;
                                        Regex regex = new Regex("<img(.|\\n)*cid:" + _inlineAttachment.ContentId + "(.|\\n)*?>");
                                        Match match = regex.Match(bodyreplaced, startAt);
                                        if (match.Success)
                                        {
                                            const float maxSize = 700;
                                            Regex.Match(match.Value, "width=(\"|\')?(?<width>\\d+)(\"|\')?").Groups.TryGetValue("width", out var w);
                                            float width = float.TryParse(w?.Value, out float tempWidth) ? tempWidth : 0;
                                            Regex.Match(match.Value, "height=(\"|\')?(?<height>\\d+)(\"|\')?").Groups.TryGetValue("height", out var h);
                                            float height = float.TryParse(h?.Value, out float tempHeight) ? tempHeight : 0;

                                            if (width > maxSize && width >= height)
                                            {
                                                float scale = maxSize / width;
                                                width = (int) (width * scale);
                                                height = (int) (height * scale);
                                            }
                                            if (height > maxSize)
                                            {
                                                float scale = maxSize / height;
                                                width = (int) (width * scale);
                                                height = (int) (height * scale);
                                            }
                                            string widthString = string.Empty;
                                            string heightString = string.Empty;
                                            if (width > 0)
                                            {
                                                widthString = " width =\"" + width +"\"";
                                            }
                                            if (height > 0)
                                            {
                                                heightString = " height =\"" + height + "\"";
                                            }
                                            string imgReplacementString = "<img "+ widthString + heightString + " style =\"margin: 1px;\" src=\"data:" + _inlineAttachment.MimeType + ";base64," + Convert.ToBase64String(_inlineAttachment.Data) + "\"/>";
                                            bodyreplaced = regex.Replace(bodyreplaced, imgReplacementString, 1, startAt);
                                            startAt = match.Index + imgReplacementString.Length;
                                        }
                                        foreach (KeyValuePair<MemoryStream, Dictionary<string, string>> attachment in attachmentsObj)
                                        {
                                            if (attachment.Value.ContainsKey("cid") && attachment.Value["cid"] == _inlineAttachment.ContentId)
                                            {
                                                attachmentsObj.Remove(attachment.Key);
                                            }
                                        }
                                    }
                                }
                            }

                            //Message Attachments
                            string attachmentsList = "";
                            foreach (KeyValuePair<MemoryStream, Dictionary<string, string>> attachment in attachmentsObj)
                            {
                                attachmentsList += (attachment.Value["filename"] + ", ");
                            }
                            if (!string.IsNullOrEmpty(attachmentsList))
                            {

                            htmlString += (@"<tr>
                            <td><b>Attachments: </b></td>
                            <td>" + attachmentsList.Remove(attachmentsList.Length - 2, 2) + "</td></tr>");
                            }

                            htmlString += (@"</table><br/>");

                            if (bodyreplaced.Substring(0, 4) == "<div")
                            {
                                bodyreplaced = htmlString + bodyreplaced;
                            } else
                            {
                                var bodyStart = Regex.Match(bodyreplaced, "<body.*?>");
                                bodyreplaced = bodyreplaced.Insert(bodyStart.Index + bodyStart.Length, htmlString);
                            }

                            bool isConverted;
                            (output, isConverted) = ConvertHTMLtoPDF(bodyreplaced, output);

                            //    //byte[] byteArray = Encoding.ASCII.GetBytes(bodyreplaced);
                            //    //using (MemoryStream messageStream = new MemoryStream(byteArray))
                            //    //{                                    
                            //        //using (WordDocument rtfDoc = new WordDocument(messageStream, Syncfusion.DocIO.FormatType.Html))
                            //        //{
                            //        //    // Replace leading tabs, issue with syncfusion
                            //        //    rtfDoc.ReplaceFirst = true;
                            //        //    var regex = new Regex(@"(\r)*(\n)*(\t)+", RegexOptions.Multiline);
                            //        //    var occurences = rtfDoc.Replace(regex, "\r\n");

                            //        //    List<Entity> pictures = rtfDoc.FindAllItemsByProperty(EntityType.Picture, "", "");

                            //        //    if (pictures != null)
                            //        //    {
                            //        //        foreach (WPicture picture in pictures.OfType<WPicture>())
                            //        //        {
                            //        //            picture.LockAspectRatio = true;
                            //        //            const float maxSize = 500;
                            //        //            if (picture.Height > maxSize && picture.Height >= picture.Width)
                            //        //            {
                            //        //                var scale = (maxSize / picture.Height) * 100;
                            //        //                picture.HeightScale = scale;
                            //        //                picture.WidthScale = scale;
                            //        //            }
                            //        //            if (picture.Width > maxSize)
                            //        //            {
                            //        //                var scale = (maxSize / picture.Width) * 100;
                            //        //                picture.HeightScale = scale;
                            //        //                picture.WidthScale = scale;
                            //        //            }
                            //        //        }
                            //        //    }

                            //        //    //Gets all the hyperlink fields in the document

                            //        //    List<Entity> fields = rtfDoc.FindAllItemsByProperty(EntityType.Field, "FieldType", FieldType.FieldHyperlink.ToString());

                            //        //    if (fields != null)
                            //        //    {
                            //        //        for (int i = 0; i < fields.Count; i++)

                            //        //        {

                            //        //            //Creates hyperlink instance from field to manipulate the hyperlink.

                            //        //            Hyperlink hyperlink = new Hyperlink(fields[i] as WField);

                            //        //            //Gets the text to display from hyperlink

                            //        //            string existingHyperlinkText = hyperlink.TextToDisplay;

                            //        //            //Removes the content between tags

                            //        //            if (!string.IsNullOrEmpty(existingHyperlinkText))
                            //        //            {
                            //        //                string modifiedTextToDisplay = RemoveContentBetweenTags(existingHyperlinkText);

                            //        //                //Sets the modified text to display to hyperlink

                            //        //                hyperlink.TextToDisplay = modifiedTextToDisplay;
                            //        //            }

                            //        //        }
                            //        //    }




                            //        //    //Sets the break-code of First section of source document as NoBreak to avoid imported from a new page

                            //        //    rtfDoc.Sections[0].BreakCode = SectionBreakCode.NoBreak;

                            //        //    //Gets the destination document page properties.

                            //        //    WPageSetup destSecPageSetup = doc.LastSection.PageSetup;

                            //        //    //Processes each section in the source Word document.

                            //        //    for (int i = 0; i < rtfDoc.Sections.Count; i++)

                            //        //    {

                            //        //        WSection sourceSection = rtfDoc.Sections[i];

                            //        //        //Sets the destination document page setup properties to the source document sections.

                            //        //        sourceSection.PageSetup.DifferentFirstPage = destSecPageSetup.DifferentFirstPage;

                            //        //        sourceSection.PageSetup.Margins = destSecPageSetup.Margins;

                            //        //        sourceSection.PageSetup.Orientation = destSecPageSetup.Orientation;

                            //        //        sourceSection.PageSetup.PageSize = destSecPageSetup.PageSize;

                            //        //    }

                            //        //    doc.ImportContent(rtfDoc, ImportOptions.UseDestinationStyles);

                            //        //    using (DocIORenderer renderer = new DocIORenderer())
                            //        //    {
                            //        //        using PdfDocument pdfDocument = renderer.ConvertToPDF(doc);
                            //        //        //Save the PDF file
                            //        //        //Close the instance of document objects
                            //        //        pdfDocument.Save(output);
                            //        //        pdfDocument.Close(true);

                            //        //    }

                            //        //}
                            //    //}
                            //}
                            ////else
                            //{
                            //    doc.LastParagraph.AppendText("This email does not have a message body.");

                            //    using (DocIORenderer renderer = new DocIORenderer())
                            //    {
                            //        using PdfDocument pdfDocument = renderer.ConvertToPDF(doc);
                            //        //Save the PDF file
                            //        //Close the instance of document objects
                            //        pdfDocument.Save(output);
                            //        pdfDocument.Close(true);

                            //    }



                            //string htmlString = GenerateHtmlfromMsg(msg);
                            //bool isConverted;
                            //(output, isConverted) = ConvertHTMLtoPDF("<h3>Welcome to the real-time HTML editor!</h3>\r\n<p>Type HTML in the textarea above, and it will magically appear in the frame below.</p>", output);




                            break;
                        }
                        catch (Exception e)
                        {
                            string errorMessage = $"Exception occured while coverting a message file, exception :  {e.Message}";
                            message = $"Exception happened while accessing the File, re-attempting count : {attempt} , Error Message : {e.Message} , Stack trace : {e.StackTrace}";
                            SerilogNS.Log.Error(message);
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
                    SerilogNS.Log.Error(message);
                }
            }
            catch (Exception ex)
            {
                SerilogNS.Log.Error($"Error happened while moving attachments on MSG File, Exception message : {ex.Message} , details : {ex.StackTrace}");
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
                //htmlString.Append(@"
                //            <html>
                //                <head>
                //                </head>
                //                <body style='border: 50px solid white;'>
                //                    ");

                htmlString.Append(@"<table style=""font-family: Times New Roman; font-size: 12pt;"">");
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
                msg.Recipients?.Where(t => t.Type == RecipientType.To).ToList()?.ForEach(toreceipient =>
                {

                    recipientName += String.Format("{0}, {1}", toreceipient.Email, toreceipient.DisplayName);

                });


                string recipientCCName = "";
                msg.Recipients?.Where(t => t.Type == RecipientType.Cc).ToList()?.ForEach(ccreceipient =>
                {

                    recipientCCName += String.Format("{0}, {1}", ccreceipient.Email, ccreceipient.DisplayName);

                });

                string recipientBccName = "";

                msg.Recipients?.Where(t => t.Type == RecipientType.Bcc).ToList()?.ForEach(bccreceipient =>
                {

                    recipientBccName += String.Format("{0}, {1}", bccreceipient.Email, bccreceipient.DisplayName);

                });

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
                //string message = @"" + msg.BodyText?.Replace("\n", "<span style='display: block;margin-bottom: 1em;'></span>").Replace("&lt;br&gt;", "<span style='display: block;margin-bottom: 1em;'></span>")?.Replace("&lt;br/&gt;", "<span style='display: block;margin-bottom: 1em;'></span>");

                //message = message.Replace("&lt;a", "<a").Replace("&lt;/a&gt;", "</a>");
                //htmlString.Append(@"<tr><td><b>Message Body: </b></td></tr>
                //                    <tr><td></td><td>" + message.Replace("&lt;br&gt;", "<span style='display: block;margin-bottom: 1em;'></span>").Replace("&lt;br/&gt;", "<span style='display: block;margin-bottom: 1em;'></span>") + "</td></tr>");
                //htmlString.Append(@"
                //                    </table>
                //                </div>");
                //htmlString.Append(@"</body></html>");
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
