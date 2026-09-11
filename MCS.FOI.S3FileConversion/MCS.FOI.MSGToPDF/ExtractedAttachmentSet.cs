using System.Collections;

namespace MCS.FOI.MSGToPDF
{
    public sealed class ExtractedAttachment
    {
        internal ExtractedAttachment(
            string temporaryFilePath,
            Dictionary<string, string> metadata)
        {
            TemporaryFilePath = temporaryFilePath;
            Metadata = metadata;
        }

        public string TemporaryFilePath { get; }
        public Dictionary<string, string> Metadata { get; }

        public Stream OpenRead() => new FileStream(
            TemporaryFilePath,
            FileMode.Open,
            FileAccess.Read,
            FileShare.Read,
            bufferSize: 81920,
            FileOptions.SequentialScan);
    }

    public sealed class ExtractedAttachmentSet : IReadOnlyCollection<ExtractedAttachment>, IDisposable
    {
        private readonly List<ExtractedAttachment> attachments = new();
        private bool disposed;

        public ExtractedAttachmentSet(string? temporaryRootPath = null)
        {
            var rootPath = temporaryRootPath ?? Path.Combine(Path.GetTempPath(), "foi-msg-conversion");
            WorkspacePath = Path.Combine(rootPath, Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(WorkspacePath);
        }

        public string WorkspacePath { get; }
        public int Count => attachments.Count;

        public ExtractedAttachment Add(
            Dictionary<string, string> metadata,
            Action<Stream> writeContent)
        {
            ObjectDisposedException.ThrowIf(disposed, this);

            var temporaryFilePath = Path.Combine(WorkspacePath, Guid.NewGuid().ToString("N"));
            try
            {
                using (var destination = new FileStream(
                    temporaryFilePath,
                    FileMode.CreateNew,
                    FileAccess.Write,
                    FileShare.None,
                    bufferSize: 81920,
                    FileOptions.SequentialScan))
                {
                    writeContent(destination);
                }

                var attachment = new ExtractedAttachment(temporaryFilePath, metadata);
                attachments.Add(attachment);
                return attachment;
            }
            catch
            {
                File.Delete(temporaryFilePath);
                throw;
            }
        }

        public bool Remove(ExtractedAttachment attachment)
        {
            ObjectDisposedException.ThrowIf(disposed, this);
            if (!attachments.Remove(attachment))
            {
                return false;
            }

            File.Delete(attachment.TemporaryFilePath);
            return true;
        }

        public IEnumerator<ExtractedAttachment> GetEnumerator() => attachments.GetEnumerator();
        IEnumerator IEnumerable.GetEnumerator() => GetEnumerator();

        public void Dispose()
        {
            if (disposed)
            {
                return;
            }

            disposed = true;
            attachments.Clear();
            if (Directory.Exists(WorkspacePath))
            {
                Directory.Delete(WorkspacePath, recursive: true);
            }
        }
    }
}
