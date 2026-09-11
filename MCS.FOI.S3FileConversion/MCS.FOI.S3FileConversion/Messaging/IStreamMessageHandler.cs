using StackExchange.Redis;

namespace MCS.FOI.S3FileConversion.Messaging;

public interface IStreamMessageHandler
{
    Task<MessageHandlingResult> HandleAsync(
        StreamEntry message,
        CancellationToken cancellationToken);
}
