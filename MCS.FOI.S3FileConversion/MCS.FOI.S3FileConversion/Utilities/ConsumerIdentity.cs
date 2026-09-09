namespace MCS.FOI.S3FileConversion.Utilities
{
    public static class ConsumerIdentity
    {
        public static (string Name, bool IsFallback) Resolve(
            string? consumerName, string machineName, int processId)
        {
            if (!string.IsNullOrWhiteSpace(consumerName))
            {
                return (consumerName.Trim(), false);
            }

            return ($"{machineName}-{processId}", true);
        }
    }
}
