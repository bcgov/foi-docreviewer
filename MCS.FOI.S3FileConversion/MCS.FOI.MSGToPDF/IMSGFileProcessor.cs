namespace MCS.FOI.MSGToPDF
{
    public interface IMSGFileProcessor
    {
        public (bool, string, Stream, Dictionary<MemoryStream, string>) ConvertToPDF();
        public Stream SourceStream { get; set; }
        public bool IsSinglePDFOutput { get; set; }
        public int FailureAttemptCount { get; set; }
        public int WaitTimeinMilliSeconds { get; set; }


    }
}
