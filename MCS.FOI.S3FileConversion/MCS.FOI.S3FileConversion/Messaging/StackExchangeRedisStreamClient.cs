using StackExchange.Redis;

namespace MCS.FOI.S3FileConversion.Messaging;

public sealed class StackExchangeRedisStreamClient : IRedisStreamClient
{
    private const string DeadLetterScript = """
        local xaddArgs = {'MAXLEN', '~', ARGV[3], '*'}
        for index = 4, #ARGV do
            table.insert(xaddArgs, ARGV[index])
        end

        local dlqId = redis.call('XADD', KEYS[2], unpack(xaddArgs))
        local ackResult = redis.pcall('XACK', KEYS[1], ARGV[1], ARGV[2])

        if type(ackResult) == 'table' and ackResult.err then
            return {dlqId, -1, ackResult.err}
        end

        return {dlqId, ackResult, ''}
        """;

    private readonly IDatabase database;

    public StackExchangeRedisStreamClient(IDatabase database)
    {
        this.database = database;
    }

    public async Task<bool> EnsureGroupAsync(
        RedisKey stream,
        RedisValue group,
        RedisValue startPosition)
    {
        try
        {
            return await database.StreamCreateConsumerGroupAsync(
                stream,
                group,
                startPosition,
                createStream: true);
        }
        catch (RedisServerException error)
            when (error.Message.StartsWith("BUSYGROUP", StringComparison.Ordinal))
        {
            return false;
        }
    }

    public Task<StreamEntry[]> ReadNewAsync(
        RedisKey stream,
        RedisValue group,
        RedisValue consumer) =>
        database.StreamReadGroupAsync(stream, group, consumer, ">");

    public async Task<AutoClaimPage> AutoClaimOneAsync(
        RedisKey stream,
        RedisValue group,
        RedisValue consumer,
        long minIdleMilliseconds,
        RedisValue startAtId)
    {
        var result = await database.StreamAutoClaimAsync(
            stream,
            group,
            consumer,
            minIdleMilliseconds,
            startAtId,
            count: 1);

        return new AutoClaimPage(
            result.NextStartId,
            result.ClaimedEntries,
            result.DeletedIds);
    }

    public async Task<long?> GetDeliveryCountAsync(
        RedisKey stream,
        RedisValue group,
        RedisValue messageId)
    {
        var pending = await database.StreamPendingMessagesAsync(
            stream,
            group,
            count: 1,
            consumerName: RedisValue.Null,
            minId: messageId,
            maxId: messageId);

        return pending.Length == 1 && pending[0].MessageId == messageId
            ? pending[0].DeliveryCount
            : null;
    }

    public Task<long> AcknowledgeAsync(
        RedisKey stream,
        RedisValue group,
        RedisValue messageId) =>
        database.StreamAcknowledgeAsync(stream, group, messageId);

    public async Task<DeadLetterWriteResult> DeadLetterAndAcknowledgeAsync(
        RedisKey sourceStream,
        RedisValue group,
        RedisValue sourceMessageId,
        RedisKey dlqStream,
        int dlqMaxLength,
        NameValueEntry[] dlqFields)
    {
        var arguments = BuildDlqArguments(
            group,
            sourceMessageId,
            dlqMaxLength,
            dlqFields);
        var rawResult = await database.ScriptEvaluateAsync(
            DeadLetterScript,
            new[] { sourceStream, dlqStream },
            arguments);
        var values = (RedisResult[]?)rawResult;
        if (values is not { Length: 3 })
        {
            throw new InvalidOperationException(
                "Redis DLQ script returned an unexpected result shape");
        }

        return new DeadLetterWriteResult(
            (RedisValue)values[0],
            (long)values[1],
            (string?)values[2] is { Length: > 0 } error ? error : null);
    }

    public static RedisValue[] BuildDlqArguments(
        RedisValue group,
        RedisValue sourceMessageId,
        int dlqMaxLength,
        NameValueEntry[] fields)
    {
        if (fields.Length == 0)
        {
            throw new ArgumentException("At least one DLQ field is required", nameof(fields));
        }

        var arguments = new RedisValue[3 + (fields.Length * 2)];
        arguments[0] = group;
        arguments[1] = sourceMessageId;
        arguments[2] = dlqMaxLength;

        for (var index = 0; index < fields.Length; index++)
        {
            arguments[3 + (index * 2)] = fields[index].Name;
            arguments[4 + (index * 2)] = fields[index].Value;
        }

        return arguments;
    }
}
