
using Serilog;
using Syncfusion.DocIO.DLS;
using Syncfusion.DocIO;
using Syncfusion.DocIORenderer;
using Syncfusion.Pdf;
using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Wordprocessing;



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
                            SourceStream.Position = 0;

                            using (var docXML = WordprocessingDocument.Open(SourceStream, false))
                            {

                                DocumentFormat.OpenXml.Wordprocessing.Body body = docXML.MainDocumentPart.Document.Body;
                                List<String> originalDates = new List<String>();
                                foreach (var textItem in body.Descendants<FieldCode>().Where(textItem => textItem.Text.Contains("DATE")))
                                {
                                    var datetext = textItem.Parent.NextSibling().NextSibling();
                                    originalDates.Add(datetext.InnerText);
                                }

                                List<Entity> datefields = wordDocument.FindAllItemsByProperty(EntityType.Field, "FieldType", FieldType.FieldDate.ToString());
                                if (datefields != null)
                                {
                                    foreach (var (datefield, i) in datefields.Select((datefield, i) => (datefield, i)))
                                    {
                                        var dateField = datefield as WField;
                                        //Takes the owner paragraph.
                                        WParagraph ownerPara = dateField.OwnerParagraph;
                                        int dateFieldIndex = ownerPara.ChildEntities.IndexOf(dateField);
                                        //Removes the date field.
                                        ownerPara.ChildEntities.Remove(dateField);
                                        //Creating a new text range with required date.
                                        WTextRange textRange = new WTextRange(ownerPara.Document);
                                        textRange.Text = originalDates[i];//"February 12, 2023";
                                                                          //Inserting the date field with the created text range.
                                        ownerPara.ChildEntities.Insert(dateFieldIndex, textRange);
                                    }
                                }
                            }

                            wordDocument.RevisionOptions.CommentDisplayMode = CommentDisplayMode.ShowInBalloons;
                            wordDocument.RevisionOptions.CommentColor = RevisionColor.Blue;
                            wordDocument.RevisionOptions.ShowMarkup = RevisionType.Deletions | RevisionType.Insertions;

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
