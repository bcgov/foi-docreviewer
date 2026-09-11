using StackExchange.Redis;

namespace MCS.FOI.S3FileConversion;

internal interface IConversionDatabase : IDisposable
{
    Task<S3AccessKeys> getAccessKeyFromDB(string bucket);

    Task recordJobStart(StreamEntry message);

    Task<Dictionary<string, Dictionary<string, string>>> recordJobEnd(
        StreamEntry message,
        bool error,
        string jobMessage,
        List<Dictionary<string, string>> attachments);
}
