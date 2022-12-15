
using Microsoft.VisualStudio.TestTools.UnitTesting;
using MCS.FOI.ExcelToPDF;
using System.IO;
using System;

namespace MCS.FOI.ExcelToPDFUnitTests
{
    [TestClass]
    public class ExcelToPDFTests
    {
        public ExcelToPDFTests()
        {
            //checkSourceRootPathENVVAR();
        }

        private void checkSourceRootPathENVVAR()
        {
            //return;
            //#if DEBUG
            //    Environment.SetEnvironmentVariable("SourceRootPath","");//Enter local path, if required on debug execution.
            //#endif
            if (string.IsNullOrEmpty(Environment.GetEnvironmentVariable("SourceRootPath")))
            {
                var errorENV = "SourceRootPath ENV VAR missing!";
                Console.WriteLine(errorENV);
                Assert.Fail(errorENV);
            }
        }
        [TestMethod]
        public void XLSConvertToPDFTest()
        {
            checkSourceRootPathENVVAR();
            bool isconverted;
            string message = string.Empty;
            Stream output = new MemoryStream();
            Stream testFile = new FileStream(Path.Combine(getExcelRootFolder(), "bc_fin_2021_supplement_estimates.xls"), FileMode.Open, FileAccess.Read);
            ExcelFileProcessor excelFileProcessor = new ExcelFileProcessor();

            //excelFileProcessor.ExcelFileName = "bc_fin_2021_supplement_estimates.xls";
            //excelFileProcessor.ExcelSourceFilePath = getExcelRootFolder();
            excelFileProcessor.SourceStream = testFile;
            excelFileProcessor.IsSinglePDFOutput = true;
            excelFileProcessor.FailureAttemptCount = 5;
            excelFileProcessor.WaitTimeinMilliSeconds = 4000;
            (isconverted, message, output) = excelFileProcessor.ConvertToPDF();

            Assert.IsTrue(isconverted == true, $"Excel to PDF Conversion failed");
            Assert.IsTrue(output.Length > 0, $"Conversion failed: output file size is zero");

            //string outputfile = Path.Combine(getExcelRootFolder(), "output", $"{Path.GetFileNameWithoutExtension(excelFileProcessor.ExcelFileName)}.pdf");
            //bool fileexists = File.Exists(outputfile);
            //Assert.IsTrue(fileexists == true, $"Converted PDF file does not exists {excelFileProcessor.ExcelFileName}");


        }

        [TestMethod]
        public void XLSXConvertToPDFTest()
        {
            checkSourceRootPathENVVAR();
            bool isconverted, isconverted1;
            string message = string.Empty;
            Stream output = new MemoryStream();
            Stream testFile = new FileStream(Path.Combine(getExcelRootFolder(), "capbudg.xlsx"), FileMode.Open, FileAccess.Read);
            ExcelFileProcessor excelFileProcessor = new ExcelFileProcessor();
            //excelFileProcessor.ExcelFileName = "capbudg.xlsx";
            //excelFileProcessor.ExcelSourceFilePath = getExcelRootFolder();
            excelFileProcessor.SourceStream = testFile;
            excelFileProcessor.IsSinglePDFOutput = true;
            excelFileProcessor.FailureAttemptCount = 5;
            excelFileProcessor.WaitTimeinMilliSeconds = 4000;
            (isconverted, message, output) = excelFileProcessor.ConvertToPDF();

            Assert.IsTrue(isconverted == true, $"Excel to PDF Conversion failed");
            Assert.IsTrue(output.Length > 0, $"Conversion failed: output file size is zero");
        }


        [TestMethod]
        public void ProblematicXLSX1ConvertToPDFTest()
        {
            checkSourceRootPathENVVAR();
            bool isconverted;
            string message = string.Empty;
            Stream output = new MemoryStream();
            Stream testFile = new FileStream(Path.Combine(getExcelRootFolder(), "IRIS Export - Masked.xlsx"), FileMode.Open, FileAccess.Read);
            ExcelFileProcessor excelFileProcessor = new ExcelFileProcessor();
            excelFileProcessor.SourceStream = testFile;
            //excelFileProcessor.ExcelFileName = "IRIS Export - Masked.xlsx";
            //excelFileProcessor.ExcelSourceFilePath = getExcelRootFolder();
            excelFileProcessor.IsSinglePDFOutput = true;
            excelFileProcessor.FailureAttemptCount = 5;
            excelFileProcessor.WaitTimeinMilliSeconds = 4000;
            (isconverted, message, output) = excelFileProcessor.ConvertToPDF();

            Assert.IsTrue(isconverted == true, $"Excel to PDF Conversion failed");
            Assert.IsTrue(output.Length > 0, $"Conversion failed: output file size is zero");

            //string outputfile = Path.Combine(getExcelRootFolder(), "output", $"{Path.GetFileNameWithoutExtension(excelFileProcessor.ExcelFileName)}.pdf");
            //bool fileexists = File.Exists(outputfile);
            //Assert.IsTrue(fileexists == true, $"Converted PDF file does not exists {excelFileProcessor.ExcelFileName}");

        }



        [TestMethod]
        //public void FolderLevelSetupExcelToPdfTest()
        //{
        //    checkSourceRootPathENVVAR();
        //    bool isconverted;
        //    string message = string.Empty;
        //    string rootLocation = getExcelRootFolder();
        //    ExcelFileProcessor excelFileProcessor = new ExcelFileProcessor();
        //    excelFileProcessor.ExcelFileName = "capbudg.xlsx";
        //    excelFileProcessor.ExcelSourceFilePath = string.Concat(rootLocation, @"\Folder2\Folder21\Folder211\");
        //    excelFileProcessor.IsSinglePDFOutput = true;
        //    excelFileProcessor.FailureAttemptCount = 5;
        //    excelFileProcessor.WaitTimeinMilliSeconds = 4000;
        //    excelFileProcessor.PdfOutputFilePath = string.Concat(rootLocation, @"\output\", excelFileProcessor.ExcelSourceFilePath.Replace(rootLocation, ""));
        //    (isconverted, message, excelFileProcessor.PdfOutputFilePath) = excelFileProcessor.ConvertToPDF();

        //    Assert.IsTrue(isconverted == true, $"Excel to PDF Conversion failed for {excelFileProcessor.ExcelFileName}");

        //    string outputfile = Path.Combine(excelFileProcessor.PdfOutputFilePath, $"{Path.GetFileNameWithoutExtension(excelFileProcessor.ExcelFileName)}.pdf");
        //    bool fileexists = File.Exists(outputfile);
        //    Assert.IsTrue(fileexists == true, $"Converted PDF file does not exists {excelFileProcessor.ExcelFileName}");
        //}


        private string getExcelRootFolder()
        {
            return Environment.GetEnvironmentVariable("SourceRootPath");
            //return "C:\\foi-docreviewer\\MCS.FOI.S3FileConversion\\MCS.FOI.ExcelToPDFUnitTests\\SourceExcel";
        }
    }
}
