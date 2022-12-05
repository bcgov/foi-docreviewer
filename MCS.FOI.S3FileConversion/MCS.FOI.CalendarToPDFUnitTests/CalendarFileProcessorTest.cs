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
        public void ProcessSimpleCalendarFilesTest()
        {

            //checkWebkitENVVAR();
            //checkSourceRootPathENVVAR();

            bool isProcessed;
            string message = string.Empty;
            Dictionary<MemoryStream, string> attachments = new Dictionary<MemoryStream, string>();
            string rootFolder = getSourceFolder();
            Stream output = new MemoryStream();
            Stream testFile = new FileStream(Path.Combine(getSourceFolder(), "test-cal.ics"), FileMode.Open, FileAccess.Read);

            //CalendarFileProcessor calendarFileProcessor = new CalendarFileProcessor();
            //calendarFileProcessor.SourceStream = testFile;
            //calendarFileProcessor.FileName = "iCalendar.ics";
            //calendarFileProcessor.FailureAttemptCount = 5;
            //calendarFileProcessor.WaitTimeinMilliSeconds = 4000;
            //calendarFileProcessor.HTMLtoPdfWebkitPath = Environment.GetEnvironmentVariable("HTMLtoPdfWebkitPath");
            //calendarFileProcessor.DestinationPath = string.Concat(rootFolder, @"\output\", calendarFileProcessor.SourcePath.Replace(rootFolder, ""));

            CalendarFileProcessor calendarFileProcessor = new CalendarFileProcessor(testFile);
            calendarFileProcessor.WaitTimeinMilliSeconds = 5000;
            calendarFileProcessor.FailureAttemptCount = 10;
            //calendarFileProcessor.HTMLtoPdfWebkitPath = "C:\\Projects\\foi-docreviewer\\MCS.FOI.S3FileConversion\\MCS.FOI.S3FileConversion\\QtBinariesWindows";
            string outputPath = Path.Combine(getSourceFolder(), "output");
            (isProcessed, message, output, attachments) = calendarFileProcessor.ProcessCalendarFiles();
            Assert.IsTrue(isProcessed == true, $"Calendar to PDF Conversion failed");
            //FileStream fileStream = new FileStream(outputPath, FileMode.OpenOrCreate, FileAccess.ReadWrite);
            //output.CopyTo(fileStream);
            //string outputFilePath = Path.Combine(calendarFileProcessor.DestinationPath, $"{Path.GetFileNameWithoutExtension(calendarFileProcessor.FileName)}.pdf");
            //bool isFileExists = File.Exists(outputFilePath);
            //Assert.IsTrue(isFileExists, $"Converted PDF file does not exists");
        }

        [TestMethod]
        public void ProcessCalendarFileWithAttachmentsTest()
        {
            //checkWebkitENVVAR();
            //checkSourceRootPathENVVAR();

            bool isProcessed;
            string message = string.Empty;
            Dictionary<MemoryStream, string> attachments = new Dictionary<MemoryStream, string>();
            string rootFolder = getSourceFolder();
            Stream output = new MemoryStream();
            Stream testFile = new FileStream(Path.Combine(getSourceFolder(), "test-with-attachments.ics"), FileMode.Open, FileAccess.Read);

            CalendarFileProcessor calendarFileProcessor = new CalendarFileProcessor(testFile);
            calendarFileProcessor.WaitTimeinMilliSeconds = 5000;
            calendarFileProcessor.FailureAttemptCount = 10;
            //calendarFileProcessor.HTMLtoPdfWebkitPath = "C:\\Projects\\foi-docreviewer\\MCS.FOI.S3FileConversion\\MCS.FOI.S3FileConversion\\QtBinariesWindows";
            //calendarFileProcessor.DestinationPath = Path.Combine(getSourceFolder(), "file-with-attachments");
            (isProcessed, message, output, attachments) = calendarFileProcessor.ProcessCalendarFiles();
            Assert.IsTrue(isProcessed == true, $"Calendar to PDF Conversion failed");

            //string outputFilePath = Path.Combine(calendarFileProcessor.DestinationPath, $"{Path.GetFileNameWithoutExtension(calendarFileProcessor.FileName)}.pdf");
            bool isAttachmentsExists = attachments.Count == 2;
            Assert.IsTrue(isAttachmentsExists, $"Attachments not found");
        }

        //[TestMethod]
        //public void ProcessFolderLevelCalendarFileTest()
        //{
        //    checkWebkitENVVAR();
        //    checkSourceRootPathENVVAR();

        //    bool isProcessed;
        //    string message = string.Empty;
        //    string rootFolder = getSourceFolder();
        //    CalendarFileProcessor calendarFileProcessor = new CalendarFileProcessor();
        //    calendarFileProcessor.SourcePath = string.Concat(rootFolder, @"\folder1\folder1\");
        //    calendarFileProcessor.DestinationPath = string.Concat(rootFolder, @"\output\", calendarFileProcessor.SourcePath.Replace(rootFolder, ""));
        //    calendarFileProcessor.FileName = "FOI-FileConversion Test iCalendar Request.ics";
        //    calendarFileProcessor.FailureAttemptCount = 5;
        //    calendarFileProcessor.WaitTimeinMilliSeconds = 4000;
        //    calendarFileProcessor.DeploymentPlatform = Platform.Windows;
        //    calendarFileProcessor.HTMLtoPdfWebkitPath = Environment.GetEnvironmentVariable("HTMLtoPdfWebkitPath");
        //    (isProcessed, message, calendarFileProcessor.DestinationPath) = calendarFileProcessor.ProcessCalendarFiles();
        //    Assert.IsTrue(isProcessed == true, $"Calendar to PDF Conversion failed for {calendarFileProcessor.FileName}");

        //    string outputFilePath = Path.Combine(calendarFileProcessor.DestinationPath, $"{Path.GetFileNameWithoutExtension(calendarFileProcessor.FileName)}.pdf");
        //    bool isFileExists = File.Exists(outputFilePath);
        //    Assert.IsTrue(isFileExists, $"Converted PDF file does not exists {calendarFileProcessor.FileName}");
        //}
        [TestMethod]
        public void ProcessComplexCalendarFilesTest()
        {
            //checkWebkitENVVAR();
            //checkSourceRootPathENVVAR();
            bool isProcessed;
            string message = string.Empty;
            Dictionary<MemoryStream, string> attachments = new Dictionary<MemoryStream, string>();
            string rootFolder = getSourceFolder();
            Stream output = new MemoryStream();
            Stream testFile = new FileStream(Path.Combine(getSourceFolder(), "test-problematic-calendar.ics"), FileMode.Open, FileAccess.Read);

            CalendarFileProcessor calendarFileProcessor = new CalendarFileProcessor(testFile);
            calendarFileProcessor.WaitTimeinMilliSeconds = 5000;
            calendarFileProcessor.FailureAttemptCount = 10;
            //calendarFileProcessor.HTMLtoPdfWebkitPath = "C:\\Projects\\foi-docreviewer\\MCS.FOI.S3FileConversion\\MCS.FOI.S3FileConversion\\QtBinariesWindows";
            //calendarFileProcessor.DestinationPath = Path.Combine(getSourceFolder(), "file-problematic");
            (isProcessed, message, output, attachments) = calendarFileProcessor.ProcessCalendarFiles();
            Assert.IsTrue(isProcessed == true, $"Calendar to PDF Conversion failed");

            //string outputFilePath = Path.Combine(calendarFileProcessor.DestinationPath, $"{Path.GetFileNameWithoutExtension(calendarFileProcessor.FileName)}.pdf");
            //bool isFileExists = File.Exists(outputFilePath);
            //Assert.IsTrue(isFileExists, $"Converted PDF file does not exists {calendarFileProcessor.FileName}");
        }

            private string getSourceFolder()
        {
            //return Environment.GetEnvironmentVariable("SourceRootPath");
            return "C:\\Projects\\foi-docreviewer\\MCS.FOI.S3FileConversion\\MCS.FOI.CalendarToPDFUnitTests\\SourceFiles";
        }
    }
}

