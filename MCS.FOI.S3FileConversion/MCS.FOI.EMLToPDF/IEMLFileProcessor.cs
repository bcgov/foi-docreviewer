namespace MCS.FOI.EMLToPDF
{
    public interface IEMLFileProcessor
    {
        public (bool, string, string, Stream) ConvertToPDF();
        public string MSGSourceFilePath { get; set; }
        public Stream SourceStream { get; set; }
        public string OutputFilePath { get; set; }
        public string MSGFileName { get; set; }
        public bool IsSinglePDFOutput { get; set; }
        public int FailureAttemptCount { get; set; }
        public int WaitTimeinMilliSeconds { get; set; }
        public string HTMLtoPdfWebkitPath { get; set; }
        public string DestinationPath { get; set; }

    }
}
