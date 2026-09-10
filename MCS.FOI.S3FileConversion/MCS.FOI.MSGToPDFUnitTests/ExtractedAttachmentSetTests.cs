using Microsoft.VisualStudio.TestTools.UnitTesting;

namespace MCS.FOI.MSGToPDF.UnitTests
{
    [TestClass]
    public class ExtractedAttachmentSetTests
    {
        [TestMethod]
        public void Dispose_RemovesDiskBackedAttachments()
        {
            var tempRoot = Path.Combine(Path.GetTempPath(), $"foi-msg-tests-{Guid.NewGuid():N}");
            string workspacePath;
            string attachmentPath;

            try
            {
                using (var attachments = new ExtractedAttachmentSet(tempRoot))
                {
                    var metadata = new Dictionary<string, string>
                    {
                        ["filename"] = "sample.txt",
                        ["size"] = "4"
                    };

                    var attachment = attachments.Add(
                        metadata,
                        destination => destination.Write(new byte[] { 1, 2, 3, 4 }));

                    workspacePath = attachments.WorkspacePath;
                    attachmentPath = attachment.TemporaryFilePath;

                    Assert.IsTrue(File.Exists(attachmentPath));
                    using var reopenedAttachment = attachment.OpenRead();
                    Assert.IsTrue(reopenedAttachment is FileStream);
                    CollectionAssert.AreEqual(
                        new byte[] { 1, 2, 3, 4 },
                        File.ReadAllBytes(attachmentPath));
                }

                Assert.IsFalse(File.Exists(attachmentPath));
                Assert.IsFalse(Directory.Exists(workspacePath));
            }
            finally
            {
                if (Directory.Exists(tempRoot))
                {
                    Directory.Delete(tempRoot, recursive: true);
                }
            }
        }
    }
}
