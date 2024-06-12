using MCS.FOI.PPTToPDF;

namespace MCS.FOI.PPTToPDFUnitTests
{
    [TestClass]
    public class PPTToPDFUnitTests
    {
        [TestMethod]
        public void PPTXToPDFTest()
        {
            bool converted;
            string message = string.Empty;
            Stream output = new MemoryStream();
            Stream testFile = new FileStream(Path.Combine(getDOCRootFolder(), "Title Lorem Ipsum.pptx"), FileMode.Open, FileAccess.Read);
            PptFileProcessor pptFileProcessor = new PptFileProcessor(testFile);

            pptFileProcessor.IsSinglePDFOutput = false;
            pptFileProcessor.WaitTimeinMilliSeconds = 5000;
            pptFileProcessor.FailureAttemptCount = 10;
            (converted, output) = pptFileProcessor.ConvertToPDF();


            SaveStreamAsFile(getDOCRootFolder(), output, "result.pdf");

            Assert.IsTrue(converted == true, $"PPT to PDF Conversion failed for {testFile}");
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

        private string getDOCRootFolder()
        {
            return "C:\\AOT\\FOI\\Source\\foi-docreviewer\\foi-docreviewer\\MCS.FOI.S3FileConversion\\MCS.FOI.PPTToPDFUnitTests\\SourceFiles";
        }
    }
}