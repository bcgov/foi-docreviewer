
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
        }

        private void checkSourceRootPathENVVAR()
        {
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

            excelFileProcessor.SourceStream = testFile;
            excelFileProcessor.IsSinglePDFOutput = true;
            excelFileProcessor.FailureAttemptCount = 5;
            excelFileProcessor.WaitTimeinMilliSeconds = 4000;
            (isconverted, message, output) = excelFileProcessor.ConvertToPDF();

            Assert.IsTrue(isconverted == true, $"Excel to PDF Conversion failed");
            Assert.IsTrue(output.Length > 0, $"Conversion failed: output file size is zero");
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
            excelFileProcessor.IsSinglePDFOutput = true;
            excelFileProcessor.FailureAttemptCount = 5;
            excelFileProcessor.WaitTimeinMilliSeconds = 4000;
            (isconverted, message, output) = excelFileProcessor.ConvertToPDF();

            Assert.IsTrue(isconverted == true, $"Excel to PDF Conversion failed");
            Assert.IsTrue(output.Length > 0, $"Conversion failed: output file size is zero");
        }

        private string getExcelRootFolder()
        {
            return Environment.GetEnvironmentVariable("SourceRootPath");
            //return "C:\\foi-docreviewer\\MCS.FOI.S3FileConversion\\MCS.FOI.ExcelToPDFUnitTests\\SourceExcel";
        }
    }
}
