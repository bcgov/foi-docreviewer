using MCS.FOI.S3FileConversion.Messaging;
using StackExchange.Redis;

namespace MCS.FOI.S3FileConversionUnitTests.Fakes;

internal sealed class FakeStreamMessageHandler : IStreamMessageHandler
{
    private readonly Func<StreamEntry, CancellationToken, Task<MessageHandlingResult>> handle;

    private FakeStreamMessageHandler(
        Func<StreamEntry, CancellationToken, Task<MessageHandlingResult>> handle)
    {
        this.handle = handle;
    }

    public List<StreamEntry> Calls { get; } = new();

    public static FakeStreamMessageHandler Returning(MessageHandlingResult result) =>
        new((_, _) => Task.FromResult(result));

    public static FakeStreamMessageHandler Throwing(Exception error) =>
        new((_, _) => Task.FromException<MessageHandlingResult>(error));

    public static FakeStreamMessageHandler Blocking(
        TaskCompletionSource<MessageHandlingResult> completion) =>
        new((_, _) => completion.Task);

    public Task<MessageHandlingResult> HandleAsync(
        StreamEntry message,
        CancellationToken cancellationToken)
    {
        Calls.Add(message);
        return handle(message, cancellationToken);
    }
}
