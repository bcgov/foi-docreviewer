using Serilog;
using Syncfusion.Pdf;
using Syncfusion.XlsIO;
using Syncfusion.XlsIORenderer;
using System.Net.Mail;

namespace MCS.FOI.ExcelToPDF
{
    /// <summary>
    /// Excel File Processor to convert XLS, XLSX to PDF, based on the Synfusion Libraries.
    /// </summary>
    public class ExcelFileProcessor : IExcelFileProcessor, IDisposable
    {

        public ExcelFileProcessor() { }

        /// <summary>
        /// Overloaded Constructor to recieve the Source Excel location and output location to save the PDF.
        /// </summary>
        /// <param name="sourceExcelFilePath"></param>
        /// <param name="excelFileName"></param>
        public ExcelFileProcessor(Stream sourceStream)
        {
            this.SourceStream = sourceStream;
        }

        /// <summary>
        /// Source Stream from S3 response
        /// </summary>
        public Stream SourceStream { get; set; }


        /// <summary>
        /// Flag to indicate to Syncfusion Xls to PDF Conversion, whether its a single page output for all spreadsheets
        /// </summary>
        public bool IsSinglePDFOutput { get; set; }

        /// <summary>
        /// Counts / tries to file convert , if that file already under access or updates or copying is still in progress
        /// </summary>
        public int FailureAttemptCount { get; set; }

        /// <summary>
        /// Wait in Milli seconds before trying next attempt
        /// </summary>
        public int WaitTimeinMilliSeconds { get; set; }

        private MemoryStream? output = null;
       /// <summary>
       /// Main Conversion Method, including Sysnfusion components, Failure recovery attempts and PDF conversion
       /// </summary>
       /// <returns>return a tuple wwith file conversion status.</returns>
        public (bool, string, Stream) ConvertToPDF()
        {
            bool converted = false;
            string message = string.Empty;
            bool _isSinglePDFOutput = IsSinglePDFOutput;
            
            try
            {
                if (SourceStream != null && SourceStream.Length > 0)
                {
                    using (ExcelEngine excelEngine = new ExcelEngine())
                    {
                        IApplication application = excelEngine.Excel;
                        SourceStream.Position = 0;

                        // Error Hanlding for workbooks that take more than X seconds to open (this will ensure this job is dropped and other conversion jobs in queue are handled correctly)
                        IWorkbook workbook = null;
                        var task = Task.Run(() => application.Workbooks.Open(SourceStream));
                        if (task.Wait(TimeSpan.FromSeconds(ConversionSettings.OpenFileWaitTimeSeconds)))
                        {
                            if (task.IsFaulted)
                            {
                                throw task.Exception.InnerException ?? task.Exception;
                            }
                            workbook = task.Result;
                        }
                        else
                        {
                            throw new TimeoutException("TimeoutError: Opening the Excel file exceeded the maximum timeout");
                        }
                            

                        for (int attempt = 1; attempt <= FailureAttemptCount && !converted; attempt++)
                        {
                            try
                            {
                                    if(attempt > 1)
                                    {
                                        SourceStream.Position = 0;
                                        workbook = application.Workbooks.Open(SourceStream);
                                    }

                                    if (workbook.Worksheets.Count > 0)
                                    {
                                        output = new MemoryStream();
                                        if (!_isSinglePDFOutput) /// if not single output, then traverse through each sheet and make seperate o/p pdfs
                                        {
                                            foreach (IWorksheet worksheet in workbook.Worksheets)
                                            {
                                                if (worksheet.Visibility == WorksheetVisibility.Visible)
                                                {
                                                    output = SaveToPdf(worksheet, output);
                                                }
                                            }
                                        }
                                        else
                                        {
                                            foreach (IWorksheet worksheet in workbook.Worksheets)
                                            {
                                                if (worksheet.Visibility == WorksheetVisibility.Visible)
                                                {
                                                    worksheet.PageSetup.PrintComments = ExcelPrintLocation.PrintSheetEnd;
                                                }
                                            }

                                            output = SaveToPdf(workbook, output);
                                        }
                                    }

                                    converted = true;
                                    message = $"File processed successfully!";
                                    workbook.Close();
                            }
                            catch(Exception e)
                            {
                                message = $"Exception happened while accessing File, re-attempting count : {attempt} , Error Message : {e.Message} , Stack trace : {e.StackTrace}";
                                Log.Error(message);
                                Console.WriteLine(message);
                                workbook.Close();
                                if (attempt == FailureAttemptCount)
                                {
                                    throw;
                                }
                                Thread.Sleep(WaitTimeinMilliSeconds);
                            }
                        }
                    }
                }
                else
                {
                    message = $"Excel File does not exist!";
                    Log.Error(message);
                }
            }
            catch (Exception ex)
            {
                converted = false;
                string errorMessage = $"Exception occured while coverting an excel file, exception :  {ex.Message}";
                string error = $"{errorMessage} , stacktrace : {ex.StackTrace}";
                Log.Error(error);
                Console.WriteLine(error);
                throw new Exception(errorMessage);
            }

            return (converted, message, output);
        }

       
        /// <summary>
        /// Save to pdf method, based on input from Excel file - Workbook vs Worksheet
        /// </summary>
        /// <param name="worksheet">worksheet object</param>
        private MemoryStream SaveToPdf(IWorksheet worksheet, MemoryStream output)
        {
            try
            {
                XlsIORenderer renderer = new XlsIORenderer();
                worksheet.PageSetup.PrintComments = ExcelPrintLocation.PrintSheetEnd;
                using var pdfDocument = renderer.ConvertToPDF(worksheet, new XlsIORendererSettings() { LayoutOptions = LayoutOptions.FitAllColumnsOnOnePage });
                pdfDocument.PageSettings.Margins = new Syncfusion.Pdf.Graphics.PdfMargins() { All = 10 };
                pdfDocument.Compression = PdfCompressionLevel.Normal;
                pdfDocument.Save(output);
               
            }
            catch (Exception ex)
            {
                string error = $"Exception Occured while coverting Excel file to PDF , exception :  {ex.Message} , stacktrace : {ex.StackTrace}";
                Console.WriteLine(error);
                throw;
            }
            return output;
        }

        /// <summary>
        ///  Save to pdf method, based on input from Excel file - Workbook vs Worksheet
        /// </summary>
        /// <param name="workbook">workbook object</param>
        private MemoryStream SaveToPdf(IWorkbook workbook, MemoryStream output)
        {
            try
            {
                XlsIORenderer renderer = new XlsIORenderer();
                using PdfDocument pdfDocument = renderer.ConvertToPDF(workbook, new XlsIORendererSettings() { LayoutOptions = LayoutOptions.FitAllColumnsOnOnePage });
                pdfDocument.Save(output);
            }
            catch (Exception ex)
            {
                string error = $"Exception Occured while coverting Excel file to PDF , exception :  {ex.Message} , stacktrace : {ex.StackTrace}";
                Console.WriteLine(error);
                throw;
            }
            return output;
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

                if(output!= null) output.Dispose();              
                // free managed resources
            }

        }

    }
}
