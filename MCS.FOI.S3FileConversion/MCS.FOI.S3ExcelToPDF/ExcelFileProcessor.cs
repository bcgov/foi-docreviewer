using Syncfusion.Pdf;
using Syncfusion.XlsIO;
using Syncfusion.XlsIORenderer;
using System;
using System.IO;
using System.Threading;
using Serilog;

namespace MCS.FOI.ExcelToPDF
{
    /// <summary>
    /// Excel File Processor to convert XLS, XLSX to PDF, based on the Synfusion Libraries.
    /// </summary>
    public class ExcelFileProcessor : IExcelFileProcessor
    {

        public ExcelFileProcessor() { }

        /// <summary>
        /// Overloaded Constructor to recieve the Source Excel location and output location to save the PDF.
        /// </summary>
        /// <param name="sourceExcelFilePath"></param>
        /// <param name="outputPdfFilePath"></param>
        /// <param name="excelFileName"></param>
        public ExcelFileProcessor(Stream sourceStream, string outputPdfFilePath)
        {
            this.SourceStream = sourceStream;
            //this.ExcelSourceFilePath = sourceExcelFilePath;
            this.PdfOutputFilePath = outputPdfFilePath;
            //this.ExcelFileName = excelFileName;
        }

        /// <summary>
        /// Source Stream from S3 response
        /// </summary>
        public Stream SourceStream { get; set; }

        /// <summary>
        /// Source Excel Path, this will be full path including sub folders/ directories
        /// </summary>
        public string ExcelSourceFilePath { get; set; }

        /// <summary>
        /// PDF output path with sub folder(s) path
        /// </summary>
        public string PdfOutputFilePath { get; set; }

        /// <summary>
        /// Source File Name
        /// </summary>
        public string ExcelFileName { get; set; }

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

       /// <summary>
       /// Main Conversion Method, including Sysnfusion components, Failure recovery attempts and PDF conversion
       /// </summary>
       /// <returns>return a tuple wwith file conversion status.</returns>
        public (bool, string, string, Stream) ConvertToPDF()
        {
            bool converted = false;
            string message = string.Empty;
            bool _isSinglePDFOutput = IsSinglePDFOutput;
            MemoryStream output = new MemoryStream();
            try
            {
                //string sourceFile = Path.Combine(ExcelSourceFilePath, ExcelFileName);
                //if (File.Exists(sourceFile))
                //{
                    using (ExcelEngine excelEngine = new ExcelEngine())
                    {
                        IApplication application = excelEngine.Excel;

                        var excelparseoptions = ExcelParseOptions.DoNotParsePivotTable;

                        for (int attempt = 1; attempt < FailureAttemptCount; attempt++)
                        {
                            Stream excelStream;
                            
                            try
                            {
                                //using (excelStream = new FileStream(sourceFile, FileMode.Open, FileAccess.Read))
                                using (excelStream = SourceStream)
                                {
                                    
                                    IWorkbook workbook = application.Workbooks.Open(excelStream, excelparseoptions);

                                    if (workbook.Worksheets.Count > 0)
                                    {
                                        if (!_isSinglePDFOutput) /// if not single output, then traverse through each sheet and make seperate o/p pdfs
                                        {
                                            foreach (IWorksheet worksheet in workbook.Worksheets)
                                            {
                                                if (worksheet.Visibility == WorksheetVisibility.Visible)
                                                {                                                   
                                                    //worksheet.UsedRange.AutofitRows();                                                    
                                                    output = saveToPdf(worksheet, output);
                                                }
                                            }
                                        }
                                        else
                                        {
                                            output = saveToPdf(workbook, output);

                                        }
                                    }

                                    converted = true;
                                    message = $"File processed successfully!";
                                    break;
                                }
                            }
                            catch(Exception e)
                            {
                                message = $"Exception happened while accessing File, re-attempting count : {attempt} , Error Message : {e.Message} , Stack trace : {e.StackTrace}";
                                Log.Error(message);
                                Console.WriteLine(message);
                                excelStream = null;
                                Thread.Sleep(WaitTimeinMilliSeconds);
                                if(attempt >= 3 && attempt < 5 && attempt < FailureAttemptCount)
                                {
                                    excelparseoptions = ExcelParseOptions.ParseWorksheetsOnDemand;
                                }                                
                                else
                                {
                                    excelparseoptions = ExcelParseOptions.DoNotParsePivotTable;
                                }
                            }
                        }

                    }
                //}
                //else
                //{
                //    message = $"{sourceFile} does not exist!";
                //    Log.Error(message);
                //    //return converted;
                //}
            }
            catch (Exception ex)
            {
                converted = false;
                string error = $"Exception occured while coverting file at {ExcelSourceFilePath} , exception :  {ex.Message} , stacktrace : {ex.StackTrace}";
                Log.Error(error);
                Console.WriteLine(error);
            }

            return (converted, message, PdfOutputFilePath, output);
        }

       
        /// <summary>
        /// Save to pdf method, based on input from Excel file - Workbook vs Worksheet
        /// </summary>
        /// <param name="worksheet">worksheet object</param>
        private MemoryStream saveToPdf(IWorksheet worksheet, MemoryStream output)
        {
            XlsIORenderer renderer = new XlsIORenderer();
            
            if (!Directory.Exists(PdfOutputFilePath))
                Directory.CreateDirectory(PdfOutputFilePath);

            string _worksheetName = FileNameUtil.GetFormattedFileName(worksheet.Name); ;
       
            string outputFileName = Path.Combine(PdfOutputFilePath, $"{Path.GetFileNameWithoutExtension(ExcelFileName)}_{_worksheetName}");
                      
            using var pdfDocument = renderer.ConvertToPDF(worksheet, new XlsIORendererSettings() { LayoutOptions = LayoutOptions.FitAllColumnsOnOnePage });
            using var stream = new FileStream($"{outputFileName}.pdf", FileMode.Create, FileAccess.Write); 
            pdfDocument.PageSettings.Margins = new Syncfusion.Pdf.Graphics.PdfMargins() { All = 10 };
            pdfDocument.Compression = PdfCompressionLevel.Normal;            
            pdfDocument.Save(stream);
            pdfDocument.Save(output);
            stream.Dispose();
            return output;

        }

        /// <summary>
        ///  Save to pdf method, based on input from Excel file - Workbook vs Worksheet
        /// </summary>
        /// <param name="workbook">workbook object</param>
        private MemoryStream saveToPdf(IWorkbook workbook, MemoryStream output)
        {
            XlsIORenderer renderer = new XlsIORenderer();
            if (!Directory.Exists(PdfOutputFilePath))
                Directory.CreateDirectory(PdfOutputFilePath);
            string outputFileName = Path.Combine(PdfOutputFilePath, $"{Path.GetFileNameWithoutExtension(ExcelFileName)}.pdf");
            PdfDocument pdfDocument = renderer.ConvertToPDF(workbook, new XlsIORendererSettings() { LayoutOptions = LayoutOptions.FitAllColumnsOnOnePage });
            Stream stream = new FileStream(outputFileName, FileMode.Create, FileAccess.ReadWrite);
            pdfDocument.Save(stream);
            pdfDocument.Save(output);
            stream.Dispose();
            return output;

        }



    }
}
