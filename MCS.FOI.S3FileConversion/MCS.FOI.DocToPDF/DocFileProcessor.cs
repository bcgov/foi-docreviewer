using static System.Net.Mime.MediaTypeNames;

using Syncfusion.OfficeChart;
using Syncfusion.DocIO;
using Syncfusion.DocIO.DLS;
using Syncfusion.DocIORenderer;
//using Syncfusion.DocToPDFConverter;
using Syncfusion.Pdf;
//using Syncfusion.OfficeChartToImageConverter;
using Serilog;



namespace MCS.FOI.DocToPDF
{
    public class DocFileProcessor : IDocFileProcessor
    {


        //public DocFileProcessor(){        }

        public DocFileProcessor(Stream SourceStream)
        {
            this.SourceStream = SourceStream;
        }

        public Stream SourceStream { get; set; }

        public int FailureAttemptCount { get; set; }

        public int WaitTimeinMilliSeconds { get; set; }

        public bool IsSinglePDFOutput { get; set; }



        public (bool, string, Stream) ConvertToPDF()
        {
            bool converted = false;
            string message = string.Empty;
            //bool _isSinglePDFOutput = IsSinglePDFOutput;
            MemoryStream output = new();
            try
            {
                for (int attempt = 1; attempt < FailureAttemptCount; attempt++)
                {
                    try
                    {
                        //Load an existing Word document
                        //WordDocument wordDocument = new WordDocument(SourceStream, FormatType.Docx);
                        DocIORenderer renderer = new();
                        //Initialize chart to image converter for converting charts during Word to pdf conversion
                        //wordDocument.ChartToImageConverter = new ChartToImageConverter();
                        //Create an instance of DocToPDFConverter

                        //DocToPDFConverter converter = new DocToPDFConverter();
                        //Convert Word document into PDF document
                        //PdfDocument pdfDocument = converter.ConvertToPDF(wordDocument); 
                        PdfDocument pdfDocument = renderer.ConvertToPDF(SourceStream);
                        //Save the PDF file
                        //Close the instance of document objects
                        pdfDocument.Save(output);
                        pdfDocument.Close(true);
                        //wordDocument.Close();
                        converted = true;
                        message = $"File processed successfully!";
                    }
                    catch (Exception e)
                    {
                        message = $"Exception happened while accessing File, re-attempting count : {attempt} , Error Message : {e.Message} , Stack trace : {e.StackTrace}";
                        Log.Error(message);
                        Console.WriteLine(message);
                        Thread.Sleep(5000);
                    }
                }
            }
            catch (Exception ex)
            {
                converted = false;
                string error = $"Exception occured while coverting Doc file, exception :  {ex.Message} , stacktrace : {ex.StackTrace}";
                Log.Error(error);
                Console.WriteLine(error);
            }
            return (converted, message, output);
        }
    }
}