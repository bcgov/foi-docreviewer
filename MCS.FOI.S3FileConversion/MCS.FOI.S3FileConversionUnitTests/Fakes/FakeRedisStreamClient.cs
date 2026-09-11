using MCS.FOI.S3FileConversion.Messaging;
using StackExchange.Redis;

namespace MCS.FOI.S3FileConversionUnitTests.Fakes;

internal sealed class FakeRedisStreamClient : IRedisStreamClient
{
    internal sealed record AutoClaimCall(
        RedisKey Stream,
        RedisValue Group,
        RedisValue Consumer,
        long MinIdleMilliseconds,
        RedisValue StartAtId,
        int Count);

    internal sealed record AcknowledgeCall(
        RedisKey Stream,
        RedisValue Group,
        RedisValue MessageId);

    internal sealed record DeadLetterCall(
        RedisKey SourceStream,
        RedisValue Group,
        RedisValue SourceMessageId,
        RedisKey DlqStream,
        int DlqMaxLength,
        NameValueEntry[] Fields);

    public bool GroupCreated { get; set; } = true;
    public StreamEntry[] ReadResult { get; set; } = Array.Empty<StreamEntry>();
    public AutoClaimPage AutoClaimResult { get; set; } =
        new("0-0", Array.Empty<StreamEntry>(), Array.Empty<RedisValue>());
    public long? DeliveryCount { get; set; } = 1;
    public long AcknowledgeResult { get; set; } = 1;
    public DeadLetterWriteResult DeadLetterResult { get; set; } = new("2-0", 1, null);
    public Exception? EnsureGroupException { get; set; }
    public Exception? ReadException { get; set; }
    public Exception? AutoClaimException { get; set; }
    public Exception? DeliveryCountException { get; set; }
    public Exception? AcknowledgeException { get; set; }
    public Exception? DeadLetterException { get; set; }
    public List<AutoClaimCall> AutoClaimCalls { get; } = new();
    public List<AcknowledgeCall> AcknowledgeCalls { get; } = new();
    public List<DeadLetterCall> DeadLetterCalls { get; } = new();
    public int EnsureGroupCallCount { get; private set; }
    public int ReadCallCount { get; private set; }

    public Task<bool> EnsureGroupAsync(
        RedisKey stream,
        RedisValue group,
        RedisValue startPosition)
    {
        EnsureGroupCallCount++;
        return EnsureGroupException is null
            ? Task.FromResult(GroupCreated)
            : Task.FromException<bool>(EnsureGroupException);
    }

    public Task<StreamEntry[]> ReadNewAsync(
        RedisKey stream,
        RedisValue group,
        RedisValue consumer)
    {
        ReadCallCount++;
        return ReadException is null
            ? Task.FromResult(ReadResult)
            : Task.FromException<StreamEntry[]>(ReadException);
    }

    public Task<AutoClaimPage> AutoClaimOneAsync(
        RedisKey stream,
        RedisValue group,
        RedisValue consumer,
        long minIdleMilliseconds,
        RedisValue startAtId)
    {
        AutoClaimCalls.Add(new AutoClaimCall(
            stream,
            group,
            consumer,
            minIdleMilliseconds,
            startAtId,
            1));
        return AutoClaimException is null
            ? Task.FromResult(AutoClaimResult)
            : Task.FromException<AutoClaimPage>(AutoClaimException);
    }

    public Task<long?> GetDeliveryCountAsync(
        RedisKey stream,
        RedisValue group,
        RedisValue messageId) =>
        DeliveryCountException is null
            ? Task.FromResult(DeliveryCount)
            : Task.FromException<long?>(DeliveryCountException);

    public Task<long> AcknowledgeAsync(
        RedisKey stream,
        RedisValue group,
        RedisValue messageId)
    {
        AcknowledgeCalls.Add(new AcknowledgeCall(stream, group, messageId));
        return AcknowledgeException is null
            ? Task.FromResult(AcknowledgeResult)
            : Task.FromException<long>(AcknowledgeException);
    }

    public Task<DeadLetterWriteResult> DeadLetterAndAcknowledgeAsync(
        RedisKey sourceStream,
        RedisValue group,
        RedisValue sourceMessageId,
        RedisKey dlqStream,
        int dlqMaxLength,
        NameValueEntry[] dlqFields)
    {
        DeadLetterCalls.Add(new DeadLetterCall(
            sourceStream,
            group,
            sourceMessageId,
            dlqStream,
            dlqMaxLength,
            dlqFields));
        return DeadLetterException is null
            ? Task.FromResult(DeadLetterResult)
            : Task.FromException<DeadLetterWriteResult>(DeadLetterException);
    }
}
