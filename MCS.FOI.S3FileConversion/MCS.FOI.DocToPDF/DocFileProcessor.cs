
using Serilog;
using Syncfusion.DocIO.DLS;
using Syncfusion.DocIORenderer;
using Syncfusion.Pdf;



namespace MCS.FOI.DocToPDF
{
    public class DocFileProcessor : IDocFileProcessor, IDisposable
    {


        public DocFileProcessor() { }

        public DocFileProcessor(Stream SourceStream)
        {
            this.SourceStream = SourceStream;
        }

        public Stream SourceStream { get; set; }

        public int FailureAttemptCount { get; set; }

        public int WaitTimeinMilliSeconds { get; set; }

        public bool IsSinglePDFOutput { get; set; }


        private MemoryStream? output = null;
        public (bool, Stream) ConvertToPDF()
        {
            bool converted = false;
            string message = string.Empty;
            bool _isSinglePDFOutput = IsSinglePDFOutput;
            output = new MemoryStream();
            try
            {
                for (int attempt = 1; attempt <= FailureAttemptCount && !converted; attempt++)
                {
                    try
                    {
                        using (WordDocument wordDocument = new WordDocument(SourceStream, Syncfusion.DocIO.FormatType.Automatic))
                        {
                           
                            wordDocument.RevisionOptions.CommentDisplayMode = CommentDisplayMode.ShowInBalloons;
                            wordDocument.RevisionOptions.CommentColor = RevisionColor.Blue;

                       
                            using (DocIORenderer renderer = new DocIORenderer())
                            {
                                using PdfDocument pdfDocument = renderer.ConvertToPDF(wordDocument);
                                //Save the PDF file
                                //Close the instance of document objects
                                pdfDocument.Save(output);
                                pdfDocument.Close(true);
                                converted = true;

                            }

                        }
                    }
                    catch (Exception e)
                    {
                        string errorMessage = $"Exception occured while coverting a document file, exception :  {e.Message}";
                        message = $"Exception happened while accessing File, re-attempting count : {attempt} , Error Message : {e.Message} , Stack trace : {e.StackTrace}";
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
                // free managed resources
            }

        }
    }
}