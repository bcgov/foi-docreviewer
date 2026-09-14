using StackExchange.Redis;

namespace MCS.FOI.S3FileConversion;

internal interface IFileConverter : IDisposable
{
    Task<(List<Dictionary<string, string>>, long)> ConvertFile(
        StreamEntry message,
        S3AccessKeys s3AccessKeys);
}
