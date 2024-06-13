
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
        public void DOCConvertToPDFTest()
        {
            bool converted;
            string message = string.Empty;
            Stream output = new MemoryStream();
            Stream testFile = new FileStream(Path.Combine(getDOCRootFolder(), "Ministers Housing Weekly 2023 12 19 DRAFT - TEST.docx"), FileMode.Open, FileAccess.Read);
            DocFileProcessor DocFileProcessor = new DocFileProcessor();

            DocFileProcessor docFileProcessor = new DocFileProcessor(testFile);
            docFileProcessor.IsSinglePDFOutput = false;
            docFileProcessor.WaitTimeinMilliSeconds = 5000;
            docFileProcessor.FailureAttemptCount = 10;
            (converted, output) = docFileProcessor.ConvertToPDF();


            SaveStreamAsFile(getDOCRootFolder(), output, "result.pdf");

            Assert.IsTrue(converted == true, $"DOC to PDF Conversion failed for {testFile}");
            Assert.IsTrue(output.Length > 0, $"Conversion failed: output file size is zero");
        }

        public static void SaveStreamAsFile(string filePath, Stream stream, string fileName)
        {
            stream.Position = 0;
             var path = Path.Combine(filePath, fileName);
            var bytesInStream = new byte[stream.Length];

            stream.Read(bytesInStream, 0, (int)bytesInStream.Length);

            using (var outputFileStream = new FileStream(path, FileMode.Create))
            {
                outputFileStream.Write(bytesInStream, 0, bytesInStream.Length);
            }
        }


        [TestMethod]
        public void ProblematicDOCXConvertToPDFTest()
        {
            bool converted;
            string message = string.Empty;
            Stream output = new MemoryStream();
            Stream testFile = new FileStream(Path.Combine(getDOCRootFolder(), "REDAX-IAO-Adobe-Redax-Guidelines.docx"), FileMode.Open, FileAccess.Read);
            DocFileProcessor DocFileProcessor = new DocFileProcessor();
            DocFileProcessor.SourceStream = testFile;

            DocFileProcessor.IsSinglePDFOutput = true;
            DocFileProcessor.FailureAttemptCount = 5;
            DocFileProcessor.WaitTimeinMilliSeconds = 4000;

            (converted, output) = DocFileProcessor.ConvertToPDF();

            SaveStreamAsFile(getDOCRootFolder(), output, "result.pdf");

            Assert.IsTrue(converted == true, $"Doc to PDF Conversion failed for {testFile}");
            Assert.IsTrue(output.Length > 0, $"Conversion failed: output file size is zero");
        }



        private string getDOCRootFolder()
        {
            return "C:\\AOT\\FOI\\Source\\foi-docreviewer\\foi-docreviewer\\MCS.FOI.S3FileConversion\\MCS.FOI.DocToPDFUnitTests\\SourceFiles";
        }
    }
}
