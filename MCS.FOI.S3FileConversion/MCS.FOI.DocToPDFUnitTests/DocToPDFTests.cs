
using Microsoft.VisualStudio.TestTools.UnitTesting;
using MCS.FOI.DocToPDF;
using System.IO;
using System;

namespace MCS.FOI.DocToPDFUnitTests
{
    [TestClass]
    public class DocToPDFTests
    {
        public DocToPDFTests()
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
        public void DOCConvertToPDFTest()
        {
            //checkSourceRootPathENVVAR();

            bool converted;
            string message = string.Empty;
            Stream output = new MemoryStream();
            Stream testFile = new FileStream(Path.Combine(getDOCRootFolder(), "simple-test-doc.docx"), FileMode.Open, FileAccess.Read);
            DocFileProcessor DocFileProcessor = new DocFileProcessor();

            DocFileProcessor docFileProcessor = new DocFileProcessor(testFile);
            docFileProcessor.IsSinglePDFOutput = false;
            docFileProcessor.WaitTimeinMilliSeconds = 5000;
            docFileProcessor.FailureAttemptCount = 10;
            //DocFileProcessor.PdfOutputFilePath = Path.Combine(getDOCRootFolder(), "output");
            (converted, output) = docFileProcessor.ConvertToPDF(); 

            
            //(isconverted, message, DocFileProcessor.PdfOutputFilePath, output) = DocFileProcessor.ConvertToPDF();

            Assert.IsTrue(converted == true, $"DOC to PDF Conversion failed for {testFile}");
            Assert.IsTrue(output.Length > 0, $"Conversion failed: output file size is zero");

            //string outputfile = Path.Combine(getExcelRootFolder(), "output", $"{Path.GetFileNameWithoutExtension(DocFileProcessor.ExcelFileName)}.pdf");
            //bool fileexists = File.Exists(outputfile);
            //Assert.IsTrue(fileexists == true, $"Converted PDF file does not exists {DocFileProcessor.ExcelFileName}");


        }


        [TestMethod]
        public void ProblematicDOCXConvertToPDFTest()
        {
            //checkSourceRootPathENVVAR();
            bool converted;
            string message = string.Empty;
            Stream output = new MemoryStream();
            Stream testFile = new FileStream(Path.Combine(getDOCRootFolder(), "REDAX-IAO-Adobe-Redax-Guidelines.docx"), FileMode.Open, FileAccess.Read);
            DocFileProcessor DocFileProcessor = new DocFileProcessor();
            DocFileProcessor.SourceStream = testFile;
            //DocFileProcessor.ExcelFileName = "IRIS Export - Masked.xlsx";
            //DocFileProcessor.ExcelSourceFilePath = getExcelRootFolder();
            DocFileProcessor.IsSinglePDFOutput = true;
            DocFileProcessor.FailureAttemptCount = 5;
            DocFileProcessor.WaitTimeinMilliSeconds = 4000;
            //DocFileProcessor.PdfOutputFilePath = Path.Combine(getDOCRootFolder(), "output");
            (converted, output) = DocFileProcessor.ConvertToPDF();

            Assert.IsTrue(converted == true, $"Doc to PDF Conversion failed for {testFile}");
            Assert.IsTrue(output.Length > 0, $"Conversion failed: output file size is zero");

            //string outputfile = Path.Combine(getExcelRootFolder(), "output", $"{Path.GetFileNameWithoutExtension(DocFileProcessor.ExcelFileName)}.pdf");
            //bool fileexists = File.Exists(outputfile);
            //Assert.IsTrue(fileexists == true, $"Converted PDF file does not exists {DocFileProcessor.ExcelFileName}");

        }



        private string getDOCRootFolder()
        {
            //return Environment.GetEnvironmentVariable("SourceRootPath");
            return "C:\\Projects\\foi-docreviewer\\MCS.FOI.S3FileConversion\\MCS.FOI.DocToPDFUnitTests\\SourceFiles";
        }
    }
}
