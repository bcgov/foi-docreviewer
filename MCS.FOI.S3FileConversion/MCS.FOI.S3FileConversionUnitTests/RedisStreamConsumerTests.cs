using System.Text.Json;
using MCS.FOI.S3FileConversion.Messaging;
using MCS.FOI.S3FileConversionUnitTests.Fakes;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using StackExchange.Redis;

namespace MCS.FOI.S3FileConversionUnitTests;

[TestClass]
public class RedisStreamConsumerTests
{
    [DataTestMethod]
    [DataRow(1L, false)]
    [DataRow(2L, false)]
    [DataRow(3L, true)]
    public async Task RetryableFailureIsDeadLetteredOnlyAtDeliveryCap(
        long deliveryCount,
        bool expectDeadLetter)
    {
        var redis = new FakeRedisStreamClient { DeliveryCount = deliveryCount };
        var handler = FakeStreamMessageHandler.Returning(
            MessageHandlingResult.Retryable(new IOException("temporary")));
        var consumer = CreateConsumer(redis, handler);

        await consumer.ProcessEntryAsync(Message("1-0"), reclaimed: false, default);

        Assert.AreEqual(expectDeadLetter ? 1 : 0, redis.DeadLetterCalls.Count);
        Assert.AreEqual(0, redis.AcknowledgeCalls.Count);
    }

    [TestMethod]
    public async Task SuccessfulMessageIsAcknowledgedExactlyOnce()
    {
        var redis = new FakeRedisStreamClient();
        var consumer = CreateConsumer(
            redis,
            FakeStreamMessageHandler.Returning(MessageHandlingResult.Succeeded()));

        await consumer.ProcessEntryAsync(Message("1-0"), reclaimed: false, default);

        Assert.AreEqual(1, redis.AcknowledgeCalls.Count);
        Assert.AreEqual("1-0", redis.AcknowledgeCalls.Single().MessageId.ToString());
        Assert.AreEqual(0, redis.DeadLetterCalls.Count);
    }

    [TestMethod]
    public async Task PermanentFailureIsDeadLetteredOnFirstDelivery()
    {
        var redis = new FakeRedisStreamClient { DeliveryCount = 1 };
        var consumer = CreateConsumer(
            redis,
            FakeStreamMessageHandler.Returning(
                MessageHandlingResult.Permanent(new InvalidDataException("invalid"))));

        await consumer.ProcessEntryAsync(Message("1-0"), reclaimed: false, default);

        Assert.AreEqual("validation_error", Field(redis.DeadLetterCalls.Single(), "reason"));
        Assert.AreEqual(0, redis.AcknowledgeCalls.Count);
    }

    [TestMethod]
    public async Task DeliveryAboveCapIsDeadLetteredWithoutCallingHandler()
    {
        var redis = new FakeRedisStreamClient { DeliveryCount = 4 };
        var handler = FakeStreamMessageHandler.Returning(MessageHandlingResult.Succeeded());
        var consumer = CreateConsumer(redis, handler);

        await consumer.ProcessEntryAsync(Message("1-0"), reclaimed: true, default);

        Assert.AreEqual(0, handler.Calls.Count);
        Assert.AreEqual("delivery_cap_exceeded", Field(redis.DeadLetterCalls.Single(), "reason"));
    }

    [TestMethod]
    public async Task MissingDeliveryCountLeavesMessageUntouched()
    {
        var redis = new FakeRedisStreamClient { DeliveryCount = null };
        var handler = FakeStreamMessageHandler.Returning(MessageHandlingResult.Succeeded());
        var consumer = CreateConsumer(redis, handler);

        await consumer.ProcessEntryAsync(Message("1-0"), reclaimed: false, default);

        Assert.AreEqual(0, handler.Calls.Count);
        Assert.AreEqual(0, redis.AcknowledgeCalls.Count);
        Assert.AreEqual(0, redis.DeadLetterCalls.Count);
    }

    [TestMethod]
    public async Task UnexpectedHandlerExceptionUsesRetryableDeliveryRule()
    {
        var redis = new FakeRedisStreamClient { DeliveryCount = 3 };
        var consumer = CreateConsumer(
            redis,
            FakeStreamMessageHandler.Throwing(new IOException("unexpected")));

        await consumer.ProcessEntryAsync(Message("1-0"), reclaimed: false, default);

        Assert.AreEqual("handler_error", Field(redis.DeadLetterCalls.Single(), "reason"));
        Assert.AreEqual(0, redis.AcknowledgeCalls.Count);
    }

    [TestMethod]
    public async Task DlqFailureNeverFallsBackToSeparateAcknowledge()
    {
        var redis = new FakeRedisStreamClient
        {
            DeadLetterException = new RedisServerException("WRONGTYPE")
        };
        var consumer = CreateConsumer(
            redis,
            FakeStreamMessageHandler.Returning(
                MessageHandlingResult.Permanent(new InvalidDataException("invalid"))));

        await Assert.ThrowsExceptionAsync<RedisServerException>(() =>
            consumer.ProcessEntryAsync(Message("1-0"), reclaimed: false, default));

        Assert.AreEqual(0, redis.AcknowledgeCalls.Count);
    }

    [TestMethod]
    public async Task DlqRecordRedactsTokenAndTruncatesErrorWithUtcTimestamp()
    {
        var redis = new FakeRedisStreamClient();
        var now = new DateTimeOffset(2026, 9, 10, 18, 30, 45, TimeSpan.Zero);
        var consumer = CreateConsumer(
            redis,
            FakeStreamMessageHandler.Returning(
                MessageHandlingResult.Permanent(new InvalidDataException(new string('x', 5_000)))),
            new FixedTimeProvider(now));
        var message = new StreamEntry("42-0", new[]
        {
            new NameValueEntry("UserToken", "secret"),
            new NameValueEntry("filename", "report.docx")
        });

        await consumer.ProcessEntryAsync(message, reclaimed: false, default);

        var call = redis.DeadLetterCalls.Single();
        Assert.AreEqual(4_000, Field(call, "error").Length);
        Assert.AreEqual("2026-09-10T18:30:45.0000000+00:00", Field(call, "failed_at"));
        using var fields = JsonDocument.Parse(Field(call, "fields"));
        Assert.AreEqual("***REDACTED***", fields.RootElement.GetProperty("UserToken").GetString());
        Assert.AreEqual("report.docx", fields.RootElement.GetProperty("filename").GetString());
    }

    [TestMethod]
    public async Task DlqAcknowledgeErrorIsPropagatedWithoutSeparateAcknowledge()
    {
        var redis = new FakeRedisStreamClient
        {
            DeadLetterResult = new DeadLetterWriteResult("2-0", -1, "NOGROUP")
        };
        var consumer = CreateConsumer(
            redis,
            FakeStreamMessageHandler.Returning(
                MessageHandlingResult.Permanent(new InvalidDataException("invalid"))));

        var error = await Assert.ThrowsExceptionAsync<InvalidOperationException>(() =>
            consumer.ProcessEntryAsync(Message("1-0"), reclaimed: false, default));

        StringAssert.Contains(error.Message, "NOGROUP");
        Assert.AreEqual(0, redis.AcknowledgeCalls.Count);
    }

    [TestMethod]
    public async Task AcknowledgeExceptionIsPropagatedWithoutDeadLettering()
    {
        var redis = new FakeRedisStreamClient
        {
            AcknowledgeException = new RedisServerException("NOGROUP")
        };
        var consumer = CreateConsumer(
            redis,
            FakeStreamMessageHandler.Returning(MessageHandlingResult.Succeeded()));

        await Assert.ThrowsExceptionAsync<RedisServerException>(() =>
            consumer.ProcessEntryAsync(Message("1-0"), reclaimed: false, default));

        Assert.AreEqual(0, redis.DeadLetterCalls.Count);
    }

    [TestMethod]
    public async Task ReclaimOneUsesConfiguredIdleTimeAndAdvancesCursor()
    {
        var redis = new FakeRedisStreamClient
        {
            DeliveryCount = 2,
            AutoClaimResult = new AutoClaimPage(
                "20-0",
                new[] { Message("10-0") },
                Array.Empty<RedisValue>())
        };
        var consumer = CreateConsumer(
            redis,
            FakeStreamMessageHandler.Returning(MessageHandlingResult.Succeeded()));

        await consumer.ReclaimOneAsync(default);

        Assert.AreEqual(1, redis.AutoClaimCalls.Single().Count);
        Assert.AreEqual(
            (long)TimeSpan.FromMinutes(150).TotalMilliseconds,
            redis.AutoClaimCalls.Single().MinIdleMilliseconds);
        Assert.AreEqual("20-0", consumer.ClaimCursor.ToString());
    }

    [TestMethod]
    public async Task TerminalClaimCursorRemainsAtScanStart()
    {
        var redis = new FakeRedisStreamClient
        {
            AutoClaimResult = new AutoClaimPage(
                "0-0",
                Array.Empty<StreamEntry>(),
                Array.Empty<RedisValue>())
        };
        var consumer = CreateConsumer(
            redis,
            FakeStreamMessageHandler.Returning(MessageHandlingResult.Succeeded()));

        await consumer.ReclaimOneAsync(default);

        Assert.AreEqual("0-0", consumer.ClaimCursor.ToString());
    }

    [TestMethod]
    public async Task DeletedClaimIdsDoNotInvokeHandler()
    {
        var redis = new FakeRedisStreamClient
        {
            AutoClaimResult = new AutoClaimPage(
                "0-0",
                Array.Empty<StreamEntry>(),
                new RedisValue[] { "9-0" })
        };
        var handler = FakeStreamMessageHandler.Returning(MessageHandlingResult.Succeeded());
        var consumer = CreateConsumer(redis, handler);

        await consumer.ReclaimOneAsync(default);

        Assert.AreEqual(0, handler.Calls.Count);
    }

    [TestMethod]
    public async Task ReclaimExceptionDoesNotPreventNewMessagePoll()
    {
        var redis = new FakeRedisStreamClient
        {
            AutoClaimException = new RedisServerException("temporary")
        };
        using var cancellation = new CancellationTokenSource();
        var consumer = CreateConsumer(
            redis,
            FakeStreamMessageHandler.Returning(MessageHandlingResult.Succeeded()),
            TimeProvider.System,
            (_, _) =>
            {
                cancellation.Cancel();
                return Task.CompletedTask;
            });

        await consumer.RunAsync(cancellation.Token);

        Assert.AreEqual(1, redis.ReadCallCount);
    }

    [TestMethod]
    public async Task ConcurrentReclaimDoesNotClaimAgainWhileHandlerIsIncomplete()
    {
        var redis = new FakeRedisStreamClient
        {
            AutoClaimResult = new AutoClaimPage(
                "20-0",
                new[] { Message("10-0") },
                Array.Empty<RedisValue>())
        };
        var completion = new TaskCompletionSource<MessageHandlingResult>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        var consumer = CreateConsumer(redis, FakeStreamMessageHandler.Blocking(completion));

        var firstClaim = consumer.ReclaimOneAsync(default);
        await WaitUntilAsync(() => redis.AutoClaimCalls.Count == 1);
        await consumer.ReclaimOneAsync(default);

        Assert.AreEqual(1, redis.AutoClaimCalls.Count);
        completion.SetResult(MessageHandlingResult.Succeeded());
        await firstClaim;
    }

    private static RedisStreamConsumer CreateConsumer(
        FakeRedisStreamClient redis,
        IStreamMessageHandler handler,
        TimeProvider? timeProvider = null,
        Func<TimeSpan, CancellationToken, Task>? delay = null) =>
        new(
            redis,
            handler,
            "file-conversion",
            "file-conversion-group",
            "consumer-one",
            RedisConsumerSettings.Load(_ => null, "file-conversion"),
            timeProvider ?? TimeProvider.System,
            delay);

    private static StreamEntry Message(string id) =>
        new(id, new[] { new NameValueEntry("filename", "report.docx") });

    private static string Field(FakeRedisStreamClient.DeadLetterCall call, string name) =>
        call.Fields.Single(field => field.Name == name).Value!;

    private static async Task WaitUntilAsync(Func<bool> predicate)
    {
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(5));
        while (!predicate())
        {
            await Task.Delay(10, timeout.Token);
        }
    }

    private sealed class FixedTimeProvider(DateTimeOffset now) : TimeProvider
    {
        public override DateTimeOffset GetUtcNow() => now;
    }
}
