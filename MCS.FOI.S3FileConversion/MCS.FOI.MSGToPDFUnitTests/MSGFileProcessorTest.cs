using Microsoft.VisualStudio.TestTools.UnitTesting;
using System;
using System.IO;
using MCS.FOI.MSGToPDF;
using Microsoft.VisualStudio.TestPlatform.CommunicationUtilities;
using Microsoft.VisualStudio.TestPlatform.Utilities;
using static System.Net.Mime.MediaTypeNames;
using System.Collections.Generic;

namespace MCS.FOI.MSGToPDF.UnitTests
{
    [TestClass]
    public class MSGFileProcessorTest
    {
        public MSGFileProcessorTest()
        {            
        }

        private void checkWebkitENVVAR()
        {
            if (string.IsNullOrEmpty(Environment.GetEnvironmentVariable("HTMLtoPdfWebkitPath")))
            {
                var errorENV = "HTMLtoPdfWebkitPath ENV VAR missing!";
                Console.WriteLine(errorENV);
                Assert.Fail(errorENV);
            }
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
        public void ProcessSimpleMSGFilesTest()
        {
            bool converted;
            string message = string.Empty;
            Dictionary<MemoryStream, Dictionary<string,string>> attachments = new Dictionary<MemoryStream, Dictionary<string, string>>();
            string rootFolder = getSourceFolder();
            Stream output = new MemoryStream();
            Stream testFile = new FileStream(Path.Combine(getSourceFolder(), "simple-test-msg-file.msg"), FileMode.Open, FileAccess.Read);
            MSGFileProcessor msgFileProcessor = new MSGFileProcessor(testFile);
            msgFileProcessor.IsSinglePDFOutput = false;
            msgFileProcessor.WaitTimeinMilliSeconds = 5000;
            msgFileProcessor.FailureAttemptCount = 10;
            (converted, message, output, attachments) = msgFileProcessor.ConvertToPDF();
            Assert.IsTrue(converted == true, $"MSG to PDF Conversion failed for {testFile}");

            SaveStreamAsFile(getSourceFolder(), output, "result_simple-test-msg-file.pdf");
        }

        [TestMethod]
        public void ProcessMSGFileWithAttachmentsTest()
        {
            bool converted;
            string message = string.Empty;
            Dictionary<MemoryStream, Dictionary<string, string>> attachments = new Dictionary<MemoryStream, Dictionary<string, string>>();
            string rootFolder = getSourceFolder();
            Stream output = new MemoryStream();
            Stream testFile = new FileStream(Path.Combine(getSourceFolder(), "Test-MSG-File-with-Attachments.msg"), FileMode.Open, FileAccess.Read);
            MSGFileProcessor msgFileProcessor = new MSGFileProcessor(testFile);
            msgFileProcessor.IsSinglePDFOutput = false;
            msgFileProcessor.WaitTimeinMilliSeconds = 5000;
            msgFileProcessor.FailureAttemptCount = 10;
            (converted, message, output, attachments) = msgFileProcessor.ConvertToPDF();
            Assert.IsTrue(converted == true, $"MSG to PDF Conversion failed for {testFile}");

            SaveStreamAsFile(getSourceFolder(), output, "result_Test-MSG-File-with-Attachments.pdf");

            bool isAttachmentsExists = attachments.Count == 3;
            Assert.IsTrue(isAttachmentsExists, $"MSG PDF file does not exists {testFile}");
        }

        private string getSourceFolder()
        {
            return "C:\\AOT\\FOI\\Source\\foi-docreviewer\\foi-docreviewer\\MCS.FOI.S3FileConversion\\MCS.FOI.MSGToPDFUnitTests\\SourceFiles";
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
    }
}

