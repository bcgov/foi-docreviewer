using Microsoft.VisualStudio.TestTools.UnitTesting;
using System;
using System.IO;
using MCS.FOI.CalendarToPDF;
using Microsoft.VisualStudio.TestPlatform.CommunicationUtilities;
using Microsoft.VisualStudio.TestPlatform.Utilities;
using static System.Net.Mime.MediaTypeNames;

namespace MCS.FOI.CalenderToPDF.UnitTests
{
    [TestClass]
    public class CalendarFileProcessorTest
    {
        public CalendarFileProcessorTest()
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
        public void ProcessSimpleCalendarFilesTest()
        {
            bool isProcessed;
            string message = string.Empty;
            Dictionary<MemoryStream, Dictionary<string,string>> attachments = new Dictionary<MemoryStream, Dictionary<string, string>>();
            string rootFolder = getSourceFolder();
            Stream output = new MemoryStream();
            Stream testFile = new FileStream(Path.Combine(getSourceFolder(), "Backlog refinement.ics"), FileMode.Open, FileAccess.Read);

            CalendarFileProcessor calendarFileProcessor = new CalendarFileProcessor(testFile);
            calendarFileProcessor.WaitTimeinMilliSeconds = 5000;
            calendarFileProcessor.FailureAttemptCount = 10;
            string outputPath = Path.Combine(getSourceFolder(), "output");
            (isProcessed, message, output, attachments) = calendarFileProcessor.ProcessCalendarFiles();
            Assert.IsTrue(isProcessed == true, $"Calendar to PDF Conversion failed");

            SaveStreamAsFile(getSourceFolder(), output, "result_Backlog refinement.pdf");
        }

        [TestMethod]
        public void ProcessCalendarFileWithAttachmentsTest()
        {
            bool isProcessed;
            string message = string.Empty;
            Dictionary<MemoryStream, Dictionary<string, string>> attachments = new Dictionary<MemoryStream, Dictionary<string, string>>();
            string rootFolder = getSourceFolder();
            Stream output = new MemoryStream();
            Stream testFile = new FileStream(Path.Combine(getSourceFolder(), "Backlog refinement.ics"), FileMode.Open, FileAccess.Read);

            CalendarFileProcessor calendarFileProcessor = new CalendarFileProcessor(testFile);
            calendarFileProcessor.WaitTimeinMilliSeconds = 5000;
            calendarFileProcessor.FailureAttemptCount = 10;

            (isProcessed, message, output, attachments) = calendarFileProcessor.ProcessCalendarFiles();
            Assert.IsTrue(isProcessed == true, $"Calendar to PDF Conversion failed");

            bool isAttachmentsExists = attachments.Count == 2;
            Assert.IsTrue(isAttachmentsExists, $"Attachments not found");

            SaveStreamAsFile(getSourceFolder(), output, "result_Backlog refinement.pdf");
        }

        [TestMethod]
        public void ProcessComplexCalendarFilesTest()
        {
            bool isProcessed;
            string message = string.Empty;
            Dictionary<MemoryStream, Dictionary<string, string>> attachments = new Dictionary<MemoryStream, Dictionary<string, string>>();
            string rootFolder = getSourceFolder();
            Stream output = new MemoryStream();
            Stream testFile = new FileStream(Path.Combine(getSourceFolder(), "test-with-attachments.ics"), FileMode.Open, FileAccess.Read);

            CalendarFileProcessor calendarFileProcessor = new CalendarFileProcessor(testFile);
            calendarFileProcessor.WaitTimeinMilliSeconds = 5000;
            calendarFileProcessor.FailureAttemptCount = 10;
            (isProcessed, message, output, attachments) = calendarFileProcessor.ProcessCalendarFiles();
            Assert.IsTrue(isProcessed == true, $"Calendar to PDF Conversion failed");

            SaveStreamAsFile(getSourceFolder(), output, "result_test-with-attachmentsr.pdf");
        }

            private string getSourceFolder()
        {
            return "C:\\AOT\\FOI\\Source\\foi-docreviewer\\foi-docreviewer\\MCS.FOI.S3FileConversion\\MCS.FOI.CalendarToPDFUnitTests\\SourceFiles";
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

