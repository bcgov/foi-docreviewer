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
            Dictionary<MemoryStream, string> attachments = new Dictionary<MemoryStream, string>();
            string rootFolder = getSourceFolder();
            Stream output = new MemoryStream();
            Stream testFile = new FileStream(Path.Combine(getSourceFolder(), "test-cal.ics"), FileMode.Open, FileAccess.Read);

            CalendarFileProcessor calendarFileProcessor = new CalendarFileProcessor(testFile);
            calendarFileProcessor.WaitTimeinMilliSeconds = 5000;
            calendarFileProcessor.FailureAttemptCount = 10;
            string outputPath = Path.Combine(getSourceFolder(), "output");
            (isProcessed, message, output, attachments) = calendarFileProcessor.ProcessCalendarFiles();
            Assert.IsTrue(isProcessed == true, $"Calendar to PDF Conversion failed");
        }

        [TestMethod]
        public void ProcessCalendarFileWithAttachmentsTest()
        {
            bool isProcessed;
            string message = string.Empty;
            Dictionary<MemoryStream, string> attachments = new Dictionary<MemoryStream, string>();
            string rootFolder = getSourceFolder();
            Stream output = new MemoryStream();
            Stream testFile = new FileStream(Path.Combine(getSourceFolder(), "test-with-attachments.ics"), FileMode.Open, FileAccess.Read);

            CalendarFileProcessor calendarFileProcessor = new CalendarFileProcessor(testFile);
            calendarFileProcessor.WaitTimeinMilliSeconds = 5000;
            calendarFileProcessor.FailureAttemptCount = 10;

            (isProcessed, message, output, attachments) = calendarFileProcessor.ProcessCalendarFiles();
            Assert.IsTrue(isProcessed == true, $"Calendar to PDF Conversion failed");

            bool isAttachmentsExists = attachments.Count == 2;
            Assert.IsTrue(isAttachmentsExists, $"Attachments not found");
        }

        [TestMethod]
        public void ProcessComplexCalendarFilesTest()
        {
            bool isProcessed;
            string message = string.Empty;
            Dictionary<MemoryStream, string> attachments = new Dictionary<MemoryStream, string>();
            string rootFolder = getSourceFolder();
            Stream output = new MemoryStream();
            Stream testFile = new FileStream(Path.Combine(getSourceFolder(), "test-problematic-calendar.ics"), FileMode.Open, FileAccess.Read);

            CalendarFileProcessor calendarFileProcessor = new CalendarFileProcessor(testFile);
            calendarFileProcessor.WaitTimeinMilliSeconds = 5000;
            calendarFileProcessor.FailureAttemptCount = 10;
            (isProcessed, message, output, attachments) = calendarFileProcessor.ProcessCalendarFiles();
            Assert.IsTrue(isProcessed == true, $"Calendar to PDF Conversion failed");
        }

            private string getSourceFolder()
        {
            return "C:\\Projects\\foi-docreviewer\\MCS.FOI.S3FileConversion\\MCS.FOI.CalendarToPDFUnitTests\\SourceFiles";
        }
    }
}

