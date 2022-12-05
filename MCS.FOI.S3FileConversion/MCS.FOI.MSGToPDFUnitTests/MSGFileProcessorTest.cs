using Microsoft.VisualStudio.TestTools.UnitTesting;
using System;
using System.IO;
using MCS.FOI.MSGToPDF;
using Microsoft.VisualStudio.TestPlatform.CommunicationUtilities;
using Microsoft.VisualStudio.TestPlatform.Utilities;
using static System.Net.Mime.MediaTypeNames;

namespace MCS.FOI.MSGToPDF.UnitTests
{
    [TestClass]
    public class MSGFileProcessorTest
    {
        public MSGFileProcessorTest()
        {            
            //checkWebkitENVVAR();
            //checkSourceRootPathENVVAR();
        }

        private void checkWebkitENVVAR()
        {

            //#if DEBUG
            //    Environment.SetEnvironmentVariable("HTMLtoPdfWebkitPath","");//Enter local path, if required on debug execution.
            //#endif

            if (string.IsNullOrEmpty(Environment.GetEnvironmentVariable("HTMLtoPdfWebkitPath")))
            {
                var errorENV = "HTMLtoPdfWebkitPath ENV VAR missing!";
                Console.WriteLine(errorENV);
                Assert.Fail(errorENV);
            }
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
        public void ProcessSimpleMSGFilesTest()
        {

            //checkWebkitENVVAR();
            //checkSourceRootPathENVVAR();

            bool converted;
            string message = string.Empty;
            Dictionary<MemoryStream, string> attachments = new Dictionary<MemoryStream, string>();
            string rootFolder = getSourceFolder();
            Stream output = new MemoryStream();
            Stream testFile = new FileStream(Path.Combine(getSourceFolder(), "simple-test-msg-file.msg"), FileMode.Open, FileAccess.Read);
            MSGFileProcessor msgFileProcessor = new MSGFileProcessor(testFile);
            msgFileProcessor.IsSinglePDFOutput = false;
            msgFileProcessor.WaitTimeinMilliSeconds = 5000;
            msgFileProcessor.FailureAttemptCount = 10;
            //msgFileProcessor.HTMLtoPdfWebkitPath = "C:\\Projects\\foi-docreviewer\\MCS.FOI.S3FileConversion\\MCS.FOI.MSGToPDFUnitTests\\QtBinariesWindows";
            //msgFileProcessor.DestinationPath = Path.Combine(getSourceFolder(), "output");
            //msgFileProcessor.DestinationPath = getSourceFolder();
            (converted, message, output, attachments) = msgFileProcessor.ConvertToPDF();
            Assert.IsTrue(converted == true, $"MSG to PDF Conversion failed for {testFile}");

            //string outputFilePath = Path.Combine(msgFileProcessor.DestinationPath, $"{Path.GetFileNameWithoutExtension("C:\\test-files\\test1.msg")}.pdf");
            //bool isFileExists = File.Exists(outputFilePath);
            //Assert.IsTrue(isFileExists, $"Converted PDF file does not exists {testFile}");
                        
        }

        [TestMethod]
        public void ProcessMSGFileWithAttachmentsTest()
        {
            //checkWebkitENVVAR();
            //checkSourceRootPathENVVAR();

            bool converted;
            string message = string.Empty;
            Dictionary<MemoryStream, string> attachments = new Dictionary<MemoryStream, string>();
            string rootFolder = getSourceFolder();
            Stream output = new MemoryStream();
            Stream testFile = new FileStream(Path.Combine(getSourceFolder(), "Test-MSG-File-with-Attachments.msg"), FileMode.Open, FileAccess.Read);
            MSGFileProcessor msgFileProcessor = new MSGFileProcessor(testFile);
            msgFileProcessor.IsSinglePDFOutput = false;
            msgFileProcessor.WaitTimeinMilliSeconds = 5000;
            msgFileProcessor.FailureAttemptCount = 10;
            //msgFileProcessor.HTMLtoPdfWebkitPath = "C:\\Projects\\foi-docreviewer\\MCS.FOI.S3FileConversion\\MCS.FOI.MSGToPDFUnitTests\\QtBinariesWindows";
            //msgFileProcessor.DestinationPath = Path.Combine(getSourceFolder(), "output");
            //msgFileProcessor.DestinationPath = getSourceFolder();
            (converted, message, output, attachments) = msgFileProcessor.ConvertToPDF();
            Assert.IsTrue(converted == true, $"MSG to PDF Conversion failed for {testFile}");

            //string outputFilePath = Path.Combine(msgFileProcessor.DestinationPath, $"{Path.GetFileNameWithoutExtension("C:\\test-files\\test1.msg")}.pdf");
            bool isAttachmentsExists = attachments.Count == 2;
            Assert.IsTrue(isAttachmentsExists, $"MSG PDF file does not exists {testFile}");
        }

        //[TestMethod]
        //public void ProcessComplexCalendarFilesTest()
        //{
        //    //checkWebkitENVVAR();
        //    //checkSourceRootPathENVVAR();
        //    bool converted;
        //    string message = string.Empty;
        //    Dictionary<MemoryStream, string> attachments = new Dictionary<MemoryStream, string>();
        //    string rootFolder = getSourceFolder();
        //    Stream output = new MemoryStream();
        //    Stream testFile = new FileStream(Path.Combine(getSourceFolder(), "test-cal.ics"), FileMode.Open, FileAccess.Read);
        //    MSGFileProcessor msgFileProcessor = new MSGFileProcessor(testFile, "C:\\test-files\\test1.msg", "test1");
        //    msgFileProcessor.IsSinglePDFOutput = false;
        //    msgFileProcessor.WaitTimeinMilliSeconds = 5000;
        //    msgFileProcessor.FailureAttemptCount = 10;
        //    msgFileProcessor.HTMLtoPdfWebkitPath = "C:\\Projects\\foi-docreviewer\\MCS.FOI.S3FileConversion\\MCS.FOI.MSGToPDFUnitTests\\QtBinariesWindows";
        //    msgFileProcessor.DestinationPath = Path.Combine(getSourceFolder(), "output");
        //    (converted, message, msgFileProcessor.DestinationPath, output, attachments) = msgFileProcessor.ConvertToPDF();
        //    Assert.IsTrue(converted == true, $"Calendar to PDF Conversion failed for {testFile}");

        //    string outputFilePath = Path.Combine(msgFileProcessor.DestinationPath, $"{Path.GetFileNameWithoutExtension("C:\\test-files\\test1.msg")}.pdf");
        //    bool isFileExists = File.Exists(outputFilePath);
        //    Assert.IsTrue(isFileExists, $"Converted PDF file does not exists {testFile}");
        //}

        private string getSourceFolder()
        {
            //return Environment.GetEnvironmentVariable("SourceRootPath");
            return "C:\\Projects\\foi-docreviewer\\MCS.FOI.S3FileConversion\\MCS.FOI.MSGToPDFUnitTests\\SourceFiles";
        }
    }
}

