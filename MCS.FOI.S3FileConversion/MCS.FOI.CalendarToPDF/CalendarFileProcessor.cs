using Ical.Net;
using Syncfusion.HtmlConverter;
using Syncfusion.Pdf;
using System;
using System.IO;
using System.Reflection.Metadata;
using System.Text;
using System.Threading;

namespace MCS.FOI.CalendarToPDF
{
    /// <summary>
    /// Calendar files (.ics) are processed and converted to pdf using syncfusion libraries
    /// </summary>
    public class CalendarFileProcessor : ICalendarFileProcessor
    {

        /// <summary>
        /// Source iCalendar Stream
        /// </summary>
        public Stream SourceStream { get; set; }

        /// <summary>
        /// Counts / tries to file convert , if that file already under access or updates or copying is still in progress
        /// </summary>
        public int FailureAttemptCount { get; set; }

        /// <summary>
        /// Wait in Milli seconds before trying next attempt
        /// </summary>
        public int WaitTimeinMilliSeconds { get; set; }

        /// <summary>
        /// Deployment platform - Linux/Windows
        /// </summary>
        public Platform DeploymentPlatform { get; set; }

        /// <summary>
        /// Success/Failure message
        /// </summary>
        public string Message { get; set; }


        public CalendarFileProcessor()
        {

        }
        public CalendarFileProcessor(Stream sourceStream)
        {
            SourceStream = sourceStream;
            Message = string.Empty;
        }

        public (bool, string, Stream, Dictionary<MemoryStream, string>) ProcessCalendarFiles()
        {
            MemoryStream output = new MemoryStream();
            bool isConverted;
            Dictionary<MemoryStream, string> attachments = new Dictionary<MemoryStream, string>();
            try
            {
                (string htmlString, attachments) = ConvertCalendartoHTML();
                (output, isConverted) = ConvertHTMLtoPDF(htmlString, output);
            }
            catch (Exception ex)
            {
                isConverted = false;
                throw ex;
            }
            return (isConverted, Message, output, attachments);
        }

        /// <summary>
        /// Converts iCalendar to HTML
        /// </summary>
        /// <returns>HTML as a string</returns>
        private (string, Dictionary<MemoryStream, string>) ConvertCalendartoHTML()
        {
            Dictionary<MemoryStream, string> attachmentsObj = new Dictionary<MemoryStream, string>();
            try
            {
                string ical = string.Empty;
                MemoryStream attachmentStream = new MemoryStream();

                if (SourceStream != null && SourceStream.Length > 0)
                { 
                    for (int attempt = 1; attempt < FailureAttemptCount; attempt++)
                    {
                        try
                        {
                            using (StreamReader sr = new StreamReader(SourceStream))
                            {
                                ical = sr.ReadToEnd();
                            }
                        }
                        catch (Exception e)
                        {
                            Console.WriteLine($"Exception happened while accessing File, re-attempting count : {attempt}");
                            Thread.Sleep(WaitTimeinMilliSeconds);
                        }
                    }
                    Calendar calendar = Calendar.Load(ical);
                    var events = calendar.Events;
                    StringBuilder htmlString = new StringBuilder();
                    htmlString.Append(@"
                        <html>
                            <head>
                            </head>
                            <body style='border: 50px solid white;'>
                                
                                ");

                    int i = 1;
                    foreach (var e in events)
                    {
                        if (e.Attachments.Count > 0)
                        {
                            foreach (var attch in e.Attachments)
                            {
                                if (attch.Data != null)
                                {
                                    attachmentStream = new MemoryStream();
                                    var file = attch.Parameters.Get("X-FILENAME");
                                    File.WriteAllBytes(file, attch.Data);
                                    attachmentStream.Write(attch.Data, 0, attch.Data.Length);
                                    attachmentsObj.Add(attachmentStream, file);
                                }
                            }
                        }
                        //Meeting Title
                        htmlString.Append(@"<div class='header" + i + "' style='padding:2% 0 2% 0; border-top:5px solid white; border-bottom: 5px solid white;'><h1>" + e.Summary + "</h1><hr><table style='border: 5px; padding: 0; font-size:15px;'>");

                        string organizer = string.Empty;
                        //Organizer Name and Email
                        if (e.Organizer != null)
                        {
                            organizer = e.Organizer.CommonName + "(" + e.Organizer.Value.AbsoluteUri + ")";

                        }
                        else
                        {
                            organizer = @"Unknown Organizer(mailto:unknownorganizer@calendar.google.com)";
                        }
                        htmlString.Append(@"<tr>
                        <td><b>From: </b></td>
                        <td>" + organizer + "</td></tr>");
                        //Attendees name and Email
                        string attName = "";
                        foreach (var attendee in e.Attendees)
                        {
                            attName += ";" + attendee.CommonName + "(" + attendee.Value.AbsoluteUri + ")";
                        }
                        if (!string.IsNullOrEmpty(attName))
                            attName = attName.Substring(1);
                        htmlString.Append(@"<tr>
                        <td><b>To: </b></td>
                        <td>" + attName + "</td></tr>");

                        //Meeting created timestamp
                        htmlString.Append(@"<tr>
                        <td><b>Sent: </b></td>
                        <td>" + e.DtStamp.Date + "</td></tr>");

                        //Priority
                        htmlString.Append(@"<tr>
                        <td><b>Priority: </b></td>
                        <td>" + e.Priority + "</td></tr>");

                        //Meeting Start Timestamp
                        htmlString.Append(@"<tr>
                        <td><b>Start Time: </b></td>
                        <td>" + e.DtStart.Date + "</td></tr>");

                        //Meeting End Timestamp
                        htmlString.Append(@"<tr>
                        <td><b>End Time: </b></td>
                        <td>" + e.DtEnd.Date + "</td></tr>");
                        //Meeting Message
                        string message = @"" + e.Description.Replace("<", "&lt;").Replace(">", "&gt;").Replace("\n", "<br>");
                        message = message.Replace("&lt;br&gt;", "<br>").Replace("&lt;br/&gt;", "<br/>");
                        message = message.Replace("&lt;a", "<a").Replace("&lt;/a&gt;", "</a>");
                        htmlString.Append(@"<tr>
                        <td><b>Description: </b></td>
                        </tr>
                        <tr><td></td><td>" + message.Replace("&lt;br&gt;", "<br>").Replace("&lt;br/&gt;", "<br/>") + "</td></tr>");
                        htmlString.Append(@"
                                </table>
                            </div><hr>");
                        i++;
                    }

                    htmlString.Append(@"
                            </body>
                        </html>");

                    return (htmlString.ToString(), attachmentsObj);
                }
                else
                {
                    string errorMessage = $"File not found";
                    return (errorMessage, attachmentsObj);
                }
            }
            catch (Exception ex)
            {
                string error = $"Exception Occured while coverting file at {SourceStream} to HTML , exception :  {ex.Message} , stacktrace : {ex.StackTrace}";
                Console.WriteLine(error);
                Message = error;
                return (error, attachmentsObj);
            }

        }

        /// <summary>
        /// Converts HTML string to PDF using syncfution library and blink engine
        /// </summary>
        /// <param name="strHTML">HTML string</param>
        /// <returns>true - if converted successfully, else false</returns>
        private (MemoryStream, bool) ConvertHTMLtoPDF(string strHTML, MemoryStream output)
        {
            bool isConverted;
            FileStream fileStream = null;
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
                Message = $"processed successfully!";
            }
            catch (Exception ex)
            {
                isConverted = false;
                string error = $"Exception Occured while coverting file at {SourceStream} to PDF , exception :  {ex.Message} , stacktrace : {ex.StackTrace}";
                Console.WriteLine(error);
                Message = error;
            }
            finally
            {
                if (fileStream != null)
                    fileStream.Dispose();
            }
            return (output, isConverted);
        }
      }

    public enum Platform
    {
        Linux = 0,
        Windows = 1
    }
}
