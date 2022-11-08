
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
            checkSourceRootPathENVVAR();
        }

        private void checkSourceRootPathENVVAR()
        {
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
            ExcelFileProcessor excelFileProcessor = new ExcelFileProcessor();
            excelFileProcessor.ExcelFileName = "bc_fin_2021_supplement_estimates.xls";
            excelFileProcessor.ExcelSourceFilePath = getExcelRootFolder();
            excelFileProcessor.IsSinglePDFOutput = true;
            excelFileProcessor.FailureAttemptCount = 5;
            excelFileProcessor.WaitTimeinMilliSeconds = 4000;
            excelFileProcessor.PdfOutputFilePath = Path.Combine(getExcelRootFolder(), "output");
            (isconverted, message, excelFileProcessor.PdfOutputFilePath) = excelFileProcessor.ConvertToPDF();

            Assert.IsTrue(isconverted == true, $"Excel to PDF Conversion failed for {excelFileProcessor.ExcelFileName}");

            string outputfile = Path.Combine(getExcelRootFolder(), "output", $"{Path.GetFileNameWithoutExtension(excelFileProcessor.ExcelFileName)}.pdf");
            bool fileexists = File.Exists(outputfile);
            Assert.IsTrue(fileexists == true, $"Converted PDF file does not exists {excelFileProcessor.ExcelFileName}");


        }

        [TestMethod]
        public void XLSXConvertToPDFTest()
        {
            checkSourceRootPathENVVAR();
            bool isconverted, isconverted1;
            string message = string.Empty;
            ExcelFileProcessor excelFileProcessor = new ExcelFileProcessor();
            excelFileProcessor.ExcelFileName = "capbudg.xlsx";
            excelFileProcessor.ExcelSourceFilePath = getExcelRootFolder();
            excelFileProcessor.IsSinglePDFOutput = true;
            excelFileProcessor.FailureAttemptCount = 5;
            excelFileProcessor.WaitTimeinMilliSeconds = 4000;
            excelFileProcessor.PdfOutputFilePath = Path.Combine(getExcelRootFolder(), "output");
            (isconverted, message, excelFileProcessor.PdfOutputFilePath) = excelFileProcessor.ConvertToPDF();

            Assert.IsTrue(isconverted == true, $"Excel to PDF Conversion failed for {excelFileProcessor.ExcelFileName}");

            string outputfile = Path.Combine(getExcelRootFolder(), "output", $"{Path.GetFileNameWithoutExtension(excelFileProcessor.ExcelFileName)}.pdf");
            bool fileexists = File.Exists(outputfile);
            Assert.IsTrue(fileexists == true, $"Converted PDF file does not exists {excelFileProcessor.ExcelFileName}");


            ExcelFileProcessor excelFileProcessor1 = new ExcelFileProcessor();
            excelFileProcessor1.ExcelFileName = "IRIS Export - Masked.xlsx";
            excelFileProcessor1.ExcelSourceFilePath = getExcelRootFolder();
            excelFileProcessor1.IsSinglePDFOutput = true;
            excelFileProcessor1.FailureAttemptCount = 5;
            excelFileProcessor1.WaitTimeinMilliSeconds = 4000;
            excelFileProcessor1.PdfOutputFilePath = Path.Combine(getExcelRootFolder(), "output");
            (isconverted1, message, excelFileProcessor.PdfOutputFilePath) = excelFileProcessor1.ConvertToPDF();

            Assert.IsTrue(isconverted1 == true, $"Excel to PDF Conversion failed for {excelFileProcessor1.ExcelFileName}");

            string outputfile1 = Path.Combine(getExcelRootFolder(), "output", $"{Path.GetFileNameWithoutExtension(excelFileProcessor1.ExcelFileName)}.pdf");
            bool fileexists1 = File.Exists(outputfile1);
            Assert.IsTrue(fileexists1 == true, $"Converted PDF file does not exists {excelFileProcessor1.ExcelFileName}");

        }


        [TestMethod]
        public void ProblematicXLSX1ConvertToPDFTest()
        {
            checkSourceRootPathENVVAR();
            bool isconverted;
            string message = string.Empty;
            ExcelFileProcessor excelFileProcessor = new ExcelFileProcessor();
            excelFileProcessor.ExcelFileName = "IRIS Export - Masked.xlsx";
            excelFileProcessor.ExcelSourceFilePath = getExcelRootFolder();
            excelFileProcessor.IsSinglePDFOutput = true;
            excelFileProcessor.FailureAttemptCount = 5;
            excelFileProcessor.WaitTimeinMilliSeconds = 4000;
            excelFileProcessor.PdfOutputFilePath = Path.Combine(getExcelRootFolder(), "output");
            (isconverted, message, excelFileProcessor.PdfOutputFilePath) = excelFileProcessor.ConvertToPDF();

            Assert.IsTrue(isconverted == true, $"Excel to PDF Conversion failed for {excelFileProcessor.ExcelFileName}");

            string outputfile = Path.Combine(getExcelRootFolder(), "output", $"{Path.GetFileNameWithoutExtension(excelFileProcessor.ExcelFileName)}.pdf");
            bool fileexists = File.Exists(outputfile);
            Assert.IsTrue(fileexists == true, $"Converted PDF file does not exists {excelFileProcessor.ExcelFileName}");

        }

        

        [TestMethod]
        public void FolderLevelSetupExcelToPdfTest()
        {
            checkSourceRootPathENVVAR();
            bool isconverted;
            string message = string.Empty;
            string rootLocation = getExcelRootFolder();
            ExcelFileProcessor excelFileProcessor = new ExcelFileProcessor();
            excelFileProcessor.ExcelFileName = "capbudg.xlsx";
            excelFileProcessor.ExcelSourceFilePath = string.Concat(rootLocation, @"\Folder2\Folder21\Folder211\");
            excelFileProcessor.IsSinglePDFOutput = true;
            excelFileProcessor.FailureAttemptCount = 5;
            excelFileProcessor.WaitTimeinMilliSeconds = 4000;
            excelFileProcessor.PdfOutputFilePath = string.Concat(rootLocation, @"\output\", excelFileProcessor.ExcelSourceFilePath.Replace(rootLocation,""));
            (isconverted, message, excelFileProcessor.PdfOutputFilePath) = excelFileProcessor.ConvertToPDF();

            Assert.IsTrue(isconverted == true, $"Excel to PDF Conversion failed for {excelFileProcessor.ExcelFileName}");

            string outputfile = Path.Combine(excelFileProcessor.PdfOutputFilePath, $"{Path.GetFileNameWithoutExtension(excelFileProcessor.ExcelFileName)}.pdf");
            bool fileexists = File.Exists(outputfile);
            Assert.IsTrue(fileexists == true, $"Converted PDF file does not exists {excelFileProcessor.ExcelFileName}");
        }


        private string getExcelRootFolder()
        {
            return Environment.GetEnvironmentVariable("SourceRootPath");
        }
    }
}
