using System.Diagnostics;
using System.Text.Json;
using Serilog;
using Serilog.Context;
using StackExchange.Redis;

namespace MCS.FOI.S3FileConversion.Messaging;

public sealed class RedisStreamConsumer
{
    internal const string RedactedValue = "***REDACTED***";
    internal const int MaximumErrorLength = 4_000;

    private readonly IRedisStreamClient redis;
    private readonly IStreamMessageHandler handler;
    private readonly RedisKey stream;
    private readonly RedisValue group;
    private readonly RedisValue consumerName;
    private readonly RedisConsumerSettings settings;
    private readonly TimeProvider timeProvider;
    private readonly Func<TimeSpan, CancellationToken, Task> delay;
    private int reclaiming;

    public RedisStreamConsumer(
        IRedisStreamClient redis,
        IStreamMessageHandler handler,
        RedisKey stream,
        RedisValue group,
        RedisValue consumerName,
        RedisConsumerSettings settings,
        TimeProvider timeProvider,
        Func<TimeSpan, CancellationToken, Task>? delay = null)
    {
        this.redis = redis;
        this.handler = handler;
        this.stream = stream;
        this.group = group;
        this.consumerName = consumerName;
        this.settings = settings;
        this.timeProvider = timeProvider;
        this.delay = delay ?? Task.Delay;
    }

    internal RedisValue ClaimCursor { get; private set; } = "0-0";

    public async Task RunAsync(CancellationToken cancellationToken)
    {
        var created = await redis.EnsureGroupAsync(
            stream,
            group,
            StreamPosition.NewMessages);
        Log.Information(
            created
                ? "Redis consumer group {ConsumerGroup} created on stream {StreamKey}"
                : "Redis consumer group {ConsumerGroup} already exists on stream {StreamKey}",
            group,
            stream);

        var nextClaimAt = timeProvider.GetUtcNow();

        while (!cancellationToken.IsCancellationRequested)
        {
            if (timeProvider.GetUtcNow() >= nextClaimAt)
            {
                await ReclaimOneSafelyAsync(cancellationToken);
                nextClaimAt = timeProvider.GetUtcNow() + settings.ClaimInterval;
            }

            var messages = await redis.ReadNewAsync(stream, group, consumerName);
            if (messages.Length == 0)
            {
                await delay(TimeSpan.FromSeconds(1), cancellationToken);
                continue;
            }

            foreach (var message in messages)
            {
                await ProcessEntryAsync(message, reclaimed: false, cancellationToken);
            }
        }
    }

    internal async Task ProcessEntryAsync(
        StreamEntry message,
        bool reclaimed,
        CancellationToken cancellationToken)
    {
        using var streamContext = LogContext.PushProperty("StreamKey", stream.ToString());
        using var groupContext = LogContext.PushProperty("ConsumerGroup", group.ToString());
        using var consumerContext = LogContext.PushProperty("ConsumerName", consumerName.ToString());
        using var messageContext = LogContext.PushProperty("MessageId", message.Id.ToString());
        using var jobContext = TryGetJobId(message, out var jobId)
            ? LogContext.PushProperty("JobId", jobId)
            : null;

        var deliveryCount = await redis.GetDeliveryCountAsync(stream, group, message.Id);
        if (deliveryCount is null)
        {
            Log.Error("Pending metadata missing for Redis message {MessageId}", message.Id);
            return;
        }

        using var deliveryContext = LogContext.PushProperty("DeliveryCount", deliveryCount.Value);
        var stopwatch = Stopwatch.StartNew();

        if (deliveryCount > settings.MaxDeliveryAttempts)
        {
            await DeadLetterAsync(
                message,
                deliveryCount.Value,
                "delivery_cap_exceeded",
                new InvalidOperationException("message exceeded delivery cap"));
            return;
        }

        MessageHandlingResult result;
        try
        {
            result = await handler.HandleAsync(message, cancellationToken);
        }
        catch (Exception error)
        {
            result = MessageHandlingResult.Retryable(error);
        }

        try
        {
            switch (result.Disposition)
            {
                case MessageDisposition.Succeeded:
                    var acknowledged = await redis.AcknowledgeAsync(stream, group, message.Id);
                    if (acknowledged != 1)
                    {
                        throw new InvalidOperationException(
                            $"Redis acknowledged {acknowledged} entries for message {message.Id}; expected one");
                    }
                    break;
                case MessageDisposition.PermanentFailure:
                    await DeadLetterAsync(
                        message,
                        deliveryCount.Value,
                        "validation_error",
                        result.Error ?? new InvalidOperationException("permanent handler failure"));
                    break;
                case MessageDisposition.RetryableFailure
                    when deliveryCount >= settings.MaxDeliveryAttempts:
                    await DeadLetterAsync(
                        message,
                        deliveryCount.Value,
                        "handler_error",
                        result.Error ?? new InvalidOperationException("retryable handler failure"));
                    break;
                case MessageDisposition.RetryableFailure:
                    Log.Warning(
                        "Redis message {MessageId} remains pending after delivery {DeliveryCount}",
                        message.Id,
                        deliveryCount);
                    break;
                default:
                    throw new InvalidOperationException(
                        $"Unknown message disposition {result.Disposition}");
            }
        }
        catch (Exception error)
        {
            Log.Error(
                error,
                "Redis delivery lifecycle operation failed for message {MessageId}",
                message.Id);
            throw;
        }
        finally
        {
            stopwatch.Stop();
            Log.Information(
                "Redis message {MessageId} processing finished with disposition {Disposition}, reclaimed {Reclaimed}, in {ElapsedMilliseconds}ms",
                message.Id,
                result.Disposition,
                reclaimed,
                stopwatch.Elapsed.TotalMilliseconds);
        }
    }

    internal static bool TryGetJobId(StreamEntry message, out long jobId) =>
        long.TryParse(message["jobid"].ToString(), out jobId);

    internal async Task ReclaimOneAsync(CancellationToken cancellationToken)
    {
        if (Interlocked.Exchange(ref reclaiming, 1) != 0)
        {
            return;
        }

        try
        {
            var page = await redis.AutoClaimOneAsync(
                stream,
                group,
                consumerName,
                (long)settings.ClaimMinIdle.TotalMilliseconds,
                ClaimCursor);
            ClaimCursor = page.NextStartId;

            foreach (var deletedId in page.DeletedIds)
            {
                Log.Warning(
                    "Redis pending entry {MessageId} was deleted from stream {StreamKey}",
                    deletedId,
                    stream);
            }

            if (page.Entries.Count > 0)
            {
                await ProcessEntryAsync(page.Entries[0], reclaimed: true, cancellationToken);
            }
        }
        finally
        {
            Volatile.Write(ref reclaiming, 0);
        }
    }

    private async Task ReclaimOneSafelyAsync(CancellationToken cancellationToken)
    {
        try
        {
            await ReclaimOneAsync(cancellationToken);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (Exception error)
        {
            Log.Error(error, "Unable to reclaim a stale Redis stream message");
        }
    }

    private async Task DeadLetterAsync(
        StreamEntry message,
        long deliveryCount,
        string reason,
        Exception error)
    {
        var fields = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var field in message.Values)
        {
            fields[field.Name.ToString()] = field.Name.ToString().Equals(
                "usertoken",
                StringComparison.OrdinalIgnoreCase)
                ? RedactedValue
                : field.Value.ToString();
        }

        var errorText = error.ToString();
        if (errorText.Length > MaximumErrorLength)
        {
            errorText = errorText[..MaximumErrorLength];
        }

        var dlqFields = new[]
        {
            new NameValueEntry("original_stream", stream.ToString()),
            new NameValueEntry("original_group", group),
            new NameValueEntry("original_message_id", message.Id),
            new NameValueEntry("reason", reason),
            new NameValueEntry("error", errorText),
            new NameValueEntry("delivery_count", deliveryCount),
            new NameValueEntry("failed_at", timeProvider.GetUtcNow().ToString("O")),
            new NameValueEntry("fields", JsonSerializer.Serialize(fields))
        };

        var result = await redis.DeadLetterAndAcknowledgeAsync(
            stream,
            group,
            message.Id,
            settings.DlqStreamKey,
            settings.DlqMaxLength,
            dlqFields);

        if (result.AcknowledgeError is not null)
        {
            throw new InvalidOperationException(
                $"Redis DLQ entry {result.DlqMessageId} was created but acknowledgement failed: {result.AcknowledgeError}");
        }

        if (result.AcknowledgedCount != 1)
        {
            throw new InvalidOperationException(
                $"Redis DLQ entry {result.DlqMessageId} was created but acknowledged {result.AcknowledgedCount} source entries; expected one");
        }

        Log.Warning(
            "Redis message {MessageId} dead-lettered as {DlqMessageId} for {Reason}",
            message.Id,
            result.DlqMessageId,
            reason);
    }
}
