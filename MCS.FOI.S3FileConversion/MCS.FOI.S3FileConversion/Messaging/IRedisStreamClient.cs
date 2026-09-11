using StackExchange.Redis;

namespace MCS.FOI.S3FileConversion.Messaging;

public sealed record AutoClaimPage(
    RedisValue NextStartId,
    IReadOnlyList<StreamEntry> Entries,
    IReadOnlyList<RedisValue> DeletedIds);

public sealed record DeadLetterWriteResult(
    RedisValue DlqMessageId,
    long AcknowledgedCount,
    string? AcknowledgeError);

public interface IRedisStreamClient
{
    Task<bool> EnsureGroupAsync(
        RedisKey stream,
        RedisValue group,
        RedisValue startPosition);

    Task<StreamEntry[]> ReadNewAsync(
        RedisKey stream,
        RedisValue group,
        RedisValue consumer);

    Task<AutoClaimPage> AutoClaimOneAsync(
        RedisKey stream,
        RedisValue group,
        RedisValue consumer,
        long minIdleMilliseconds,
        RedisValue startAtId);

    Task<long?> GetDeliveryCountAsync(
        RedisKey stream,
        RedisValue group,
        RedisValue messageId);

    Task<long> AcknowledgeAsync(
        RedisKey stream,
        RedisValue group,
        RedisValue messageId);

    Task<DeadLetterWriteResult> DeadLetterAndAcknowledgeAsync(
        RedisKey sourceStream,
        RedisValue group,
        RedisValue sourceMessageId,
        RedisKey dlqStream,
        int dlqMaxLength,
        NameValueEntry[] dlqFields);
}
