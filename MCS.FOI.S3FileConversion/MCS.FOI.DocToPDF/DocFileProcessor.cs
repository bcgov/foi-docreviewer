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


        public DocFileProcessor(){        }

        public DocFileProcessor(Stream SourceStream)
        {
            this.SourceStream = SourceStream;
        }

        public Stream SourceStream { get; set; }

        public int FailureAttemptCount { get; set; }

        public int WaitTimeinMilliSeconds { get; set; }

        public bool IsSinglePDFOutput { get; set; }



        public (bool, Stream) ConvertToPDF()
        {
            bool converted = false;
            string message = string.Empty;
            bool _isSinglePDFOutput = IsSinglePDFOutput;
            MemoryStream output = new MemoryStream();
            try
            {
                for (int attempt = 1; attempt < FailureAttemptCount; attempt++)
                {
                    try
                    {
                        DocIORenderer renderer = new DocIORenderer();
                        PdfDocument pdfDocument = renderer.ConvertToPDF(SourceStream);
                        //Save the PDF file
                        //Close the instance of document objects
                        pdfDocument.Save(output);
                        pdfDocument.Close(true);
                        converted = true;

                    }
                    catch (Exception e)
                    {
                        message = $"Exception happened while accessing File, re-attempting count : {attempt} , Error Message : {e.Message} , Stack trace : {e.StackTrace}";
                        Log.Error(message);
                        Console.WriteLine(message);
                        if (attempt == FailureAttemptCount)
                        {
                            throw;
                        }
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
                throw;
            }
            return (converted, output);
        }
    }
}