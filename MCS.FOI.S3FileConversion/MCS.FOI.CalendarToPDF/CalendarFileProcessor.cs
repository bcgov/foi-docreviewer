using Ical.Net;
using Syncfusion.HtmlConverter;
using Syncfusion.Pdf;
using System.Runtime.Serialization;
using System.Text;

namespace MCS.FOI.CalendarToPDF
{
    /// <summary>
    /// Calendar files (.ics) are processed and converted to pdf using syncfusion libraries
    /// </summary>
    public class CalendarFileProcessor : ICalendarFileProcessor ,  IDisposable
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

        /// <summary>
        /// Success/Failure message
        /// </summary>
        public string Message { get; set; }


        private Dictionary<MemoryStream, Dictionary<string, string>> attachmentsObj = null;
        private Dictionary<MemoryStream, Dictionary<string, string>> attachments = null;
        private MemoryStream? attachmentStream = null;
        private MemoryStream? output = null;

        public CalendarFileProcessor()
        {

        }
        public CalendarFileProcessor(Stream sourceStream)
        {
            SourceStream = sourceStream;
            Message = string.Empty;
        }

        public (bool, string, Stream, Dictionary<MemoryStream, Dictionary<string, string>>) ProcessCalendarFiles()
        {
            output = new();
            bool isConverted;
            
            try
            {
                (string htmlString, attachments) = ConvertCalendartoHTML();
                (output, isConverted) = ConvertHTMLtoPDF(htmlString, output);
            }
            catch (Exception e)
            {
                throw;
            }
            return (isConverted, Message, output, attachments);
        }

        /// <summary>
        /// Converts iCalendar to HTML
        /// </summary>
        /// <returns>HTML as a string</returns>
        private (string, Dictionary<MemoryStream, Dictionary<string, string>>) ConvertCalendartoHTML()
        {           
            Calendar calendar = new Calendar();
            bool isReadCompleted = false;
            try
            {
                string ical = string.Empty;


                if (SourceStream != null && SourceStream.Length > 0)
                {
                    attachmentsObj = new();
                    for (int attempt = 1; attempt <= FailureAttemptCount && !isReadCompleted; attempt++)
                    {
                        try
                        {
                            long position = SourceStream.Position;
                            SourceStream.Seek(0, SeekOrigin.Begin);
                            using StreamReader sr = new(SourceStream);
                            ical = sr.ReadToEnd();
                            SourceStream.Seek(position, SeekOrigin.Begin);
                            isReadCompleted = true;
                            break; // this is needed to escape out of loop above!
                        }
                        catch (Exception e)
                        {
                            Console.WriteLine($"Exception happened while accessing File, re-attempting count : {attempt}");
                            Thread.Sleep(WaitTimeinMilliSeconds);
                            if (attempt == FailureAttemptCount)
                            {
                                throw;
                            }
                        }
                    }
                     calendar = Calendar.Load(ical);

                        var events = calendar.Events;
                    StringBuilder htmlString = new();
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
                                    //File.WriteAllBytes(file, attch.Data);
                                    attachmentStream.Write(attch.Data, 0, attch.Data.Length);
                                    Dictionary<string, string> attachmentInfo = new Dictionary<string, string>();
                                    string filename = attch.Parameters.Get("X-FILENAME");
                                    attachmentInfo.Add("filename", filename);
                                    attachmentInfo.Add("s3filename", filename);
                                    attachmentInfo.Add("size", attch.Data.Length.ToString());
                                    attachmentsObj.Add(attachmentStream, attachmentInfo);
                                    //attachmentsObj.Add(attachmentStream, file);
                                }
                            }
                        }
                        //Meeting Title
                        htmlString.Append(@"<div class='header" + i + "' style='padding:2% 0 2% 0; border-top:5px solid white; border-bottom: 5px solid white;'><h1 style='font-size: 3em'>" + e.Summary + "</h1><hr><table style='border: 5px; padding: 0; font-size:35px;'>");

                        string organizer = string.Empty;
                        //Organizer Name and Email
                        if (e.Organizer != null)
                        {
                            try
                            {
                                organizer = e.Organizer.CommonName + "(" + e.Organizer.Value.AbsoluteUri + ")";
                            }
                            catch
                            {

                                organizer = @"Unknown Organizer";
                            }

                        }
                        else
                        {
                            organizer = @"Unknown Organizer(mailto:unknownorganizer@calendar.bcgov.ca)";
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
                        <td>" + GetPSTTime(e.DtStamp.Date) + "</td></tr>");

                        //Priority
                        htmlString.Append(@"<tr>
                        <td><b>Priority: </b></td>
                        <td>" + e.Priority + "</td></tr>");

                        //Meeting Start Timestamp
                        htmlString.Append(@"<tr>
                        <td><b>Start Time: </b></td>
                        <td>" + GetPSTTime(e.DtStart.Value) + "</td></tr>");

                        //Meeting End Timestamp
                        htmlString.Append(@"<tr>
                        <td><b>End Time: </b></td>
                        <td>" + GetPSTTime(e.DtEnd.Value) + "</td></tr>");
                        //Meeting Message
                        string message = @"" + e.Description?.Replace("\n", "<br>");
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
            catch (SerializationException ex)
            {
                string error = $"SerializationException Occured while coverting calendar file to HTML.";
                Console.WriteLine(error);
                throw new SerializationException(error);

            }
            catch (Exception ex)
            {
                string error = $"Exception Occured while coverting calendar file to HTML , exception :  {ex.Message} , stacktrace : {ex.StackTrace}";
                Console.WriteLine(error);
                Message = error;
                throw new Exception(ex.Message);
            }
            finally
            {
                if (SourceStream != null)
                    SourceStream.Dispose();

                if(calendar!=null)
                    calendar.Dispose();
            }

        }


        private  DateTime GetPSTTime(DateTime _timetoconvert)
        {
            DateTime converteddate = _timetoconvert;
            if (TimeZone.CurrentTimeZone.StandardName != "Pacific Standard Time" || _timetoconvert.Kind == DateTimeKind.Utc )
            {

                converteddate = TimeZoneInfo.ConvertTimeBySystemTimeZoneId(converteddate, "Pacific Standard Time");

            }

            return converteddate;
        }



        /// <summary>
        /// Converts HTML string to PDF using syncfution library and blink engine
        /// </summary>
        /// <param name="strHTML">HTML string</param>
        /// <returns>true - if converted successfully, else false</returns>
        private (MemoryStream, bool) ConvertHTMLtoPDF(string strHTML, MemoryStream output)
        {
            bool isConverted;
            try
            {
                //Initialize HTML to PDF converter with Blink rendering engine
                HtmlToPdfConverter htmlConverter = new(HtmlRenderingEngine.Blink);
                BlinkConverterSettings settings = new()
                {
                    EnableHyperLink = false
                };
                //Set command line arguments to run without sandbox.
                settings.CommandLineArguments.Add("--no-sandbox");
                //settings.BlinkPath = Path.Combine("/", "BlinkBinariesLinux");
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
                string error = $"Exception Occured while coverting file to PDF , exception :  {ex.Message} , stacktrace : {ex.StackTrace}";
                Console.WriteLine(error);
                Message = error;
                throw;
            }
            return (output, isConverted);
        }


        public void Dispose()
        {
            Dispose(true);
            GC.SuppressFinalize(this);
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
                if (attachments != null) attachments = null;
                // free managed resources
            }

        }
    }
}
