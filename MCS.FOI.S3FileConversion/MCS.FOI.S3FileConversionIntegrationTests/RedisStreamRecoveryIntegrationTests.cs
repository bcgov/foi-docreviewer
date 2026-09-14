using System.Text.Json;
using MCS.FOI.S3FileConversion.Messaging;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using StackExchange.Redis;

namespace MCS.FOI.S3FileConversionIntegrationTests;

[TestClass]
[TestCategory("Integration")]
[DoNotParallelize]
public sealed class RedisStreamRecoveryIntegrationTests
{
    [TestMethod]
    public async Task AutoClaimTransfersPendingOwnershipAndIncrementsDeliveryCount()
    {
        var connectionString = RedisConnectionString();
        await using var redis = await ConnectionMultiplexer.ConnectAsync(connectionString);
        var database = redis.GetDatabase();
        var suffix = Guid.NewGuid().ToString("N");
        RedisKey stream = $"file-conversion-recovery-{suffix}";
        RedisValue group = $"recovery-group-{suffix}";

        try
        {
            var messageId = await database.StreamAddAsync(stream, MessageFields());
            await database.StreamCreateConsumerGroupAsync(stream, group, "0-0");
            var delivered = await database.StreamReadGroupAsync(
                stream,
                group,
                "dead-consumer",
                ">");
            Assert.AreEqual(messageId, delivered.Single().Id);

            var client = new StackExchangeRedisStreamClient(database);
            var claimed = await client.AutoClaimOneAsync(
                stream,
                group,
                "recovery-consumer",
                minIdleMilliseconds: 0,
                startAtId: "0-0");
            var pending = await database.StreamPendingMessagesAsync(
                stream,
                group,
                count: 1,
                consumerName: "recovery-consumer");

            Assert.AreEqual(messageId, claimed.Entries.Single().Id);
            Assert.AreEqual(
                "recovery-consumer",
                pending.Single().ConsumerName.ToString());
            Assert.AreEqual(2, pending.Single().DeliveryCount);
        }
        finally
        {
            await database.KeyDeleteAsync(stream);
        }
    }

    [TestMethod]
    public async Task ThirdRetryableDeliveryMovesMessageToRedactedDlq()
    {
        var connectionString = RedisConnectionString();
        await using var redis = await ConnectionMultiplexer.ConnectAsync(connectionString);
        var database = redis.GetDatabase();
        var suffix = Guid.NewGuid().ToString("N");
        RedisKey stream = $"file-conversion-recovery-{suffix}";
        RedisKey dlq = $"{stream}:dlq";
        RedisValue group = $"recovery-group-{suffix}";

        try
        {
            var messageId = await database.StreamAddAsync(stream, MessageFields());
            await database.StreamCreateConsumerGroupAsync(stream, group, "0-0");
            await database.StreamReadGroupAsync(stream, group, "dead-consumer", ">");
            await database.StreamAutoClaimAsync(
                stream,
                group,
                "temporary-consumer",
                minIdleTimeInMs: 0,
                startAtId: "0-0",
                count: 1);

            var consumer = Consumer(
                database,
                stream,
                group,
                dlq,
                MessageHandlingResult.Retryable(new IOException("temporary")));
            await consumer.ReclaimOneAsync(default);

            Assert.AreEqual(
                0,
                (await database.StreamPendingAsync(stream, group)).PendingMessageCount);
            var dlqEntries = await database.StreamRangeAsync(dlq);
            Assert.AreEqual(1, dlqEntries.Length);
            Assert.AreEqual(
                messageId.ToString(),
                dlqEntries[0]["original_message_id"].ToString());
            using var originalFields = JsonDocument.Parse(
                dlqEntries[0]["fields"].ToString());
            Assert.AreEqual(
                "***REDACTED***",
                originalFields.RootElement.GetProperty("usertoken").GetString());
        }
        finally
        {
            await database.KeyDeleteAsync(new[] { stream, dlq });
        }
    }

    [TestMethod]
    public async Task DlqWriteFailureLeavesOriginalPending()
    {
        var connectionString = RedisConnectionString();
        await using var redis = await ConnectionMultiplexer.ConnectAsync(connectionString);
        var database = redis.GetDatabase();
        var suffix = Guid.NewGuid().ToString("N");
        RedisKey stream = $"file-conversion-recovery-{suffix}";
        RedisKey dlq = $"{stream}:dlq";
        RedisValue group = $"recovery-group-{suffix}";

        try
        {
            await database.StreamAddAsync(stream, MessageFields());
            await database.StreamCreateConsumerGroupAsync(stream, group, "0-0");
            var message = (await database.StreamReadGroupAsync(
                stream,
                group,
                "recovery-consumer",
                ">"))
                .Single();
            await database.StringSetAsync(dlq, "wrong-type");
            var consumer = Consumer(
                database,
                stream,
                group,
                dlq,
                MessageHandlingResult.Permanent(new InvalidDataException("invalid")));

            var error = await Assert.ThrowsExceptionAsync<RedisServerException>(() =>
                consumer.ProcessEntryAsync(message, reclaimed: false, default));

            StringAssert.Contains(error.Message, "WRONGTYPE");
            Assert.AreEqual(
                1,
                (await database.StreamPendingAsync(stream, group)).PendingMessageCount);
        }
        finally
        {
            await database.KeyDeleteAsync(new[] { stream, dlq });
        }
    }

    private static RedisStreamConsumer Consumer(
        IDatabase database,
        RedisKey stream,
        RedisValue group,
        RedisKey dlq,
        MessageHandlingResult result) =>
        new(
            new StackExchangeRedisStreamClient(database),
            new StubHandler(result),
            stream,
            group,
            "recovery-consumer",
            new RedisConsumerSettings(
                TimeSpan.Zero,
                TimeSpan.FromSeconds(1),
                3,
                dlq.ToString(),
                100),
            TimeProvider.System);

    private static NameValueEntry[] MessageFields() =>
    [
        new NameValueEntry("filename", "report.docx"),
        new NameValueEntry("usertoken", "integration-secret")
    ];

    private static string RedisConnectionString()
    {
        var connectionString = Environment.GetEnvironmentVariable("REDIS_CONNECTION_STRING");
        if (string.IsNullOrWhiteSpace(connectionString))
        {
            Assert.Inconclusive("Run this integration test through ./integration/run.sh");
        }

        return connectionString!;
    }

    private sealed class StubHandler(MessageHandlingResult result) : IStreamMessageHandler
    {
        public Task<MessageHandlingResult> HandleAsync(
            StreamEntry message,
            CancellationToken cancellationToken) => Task.FromResult(result);
    }
}
