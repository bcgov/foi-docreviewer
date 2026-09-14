using MCS.FOI.S3FileConversion;
using MCS.FOI.S3FileConversion.Messaging;
using MCS.FOI.S3FileConversionUnitTests.Fakes;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using StackExchange.Redis;

namespace MCS.FOI.S3FileConversionUnitTests;

[TestClass]
public class FileConversionMessageHandlerTests
{
    private static readonly NameValueEntry[] ValidFields =
    {
        new("s3filepath", "https://s3.example.test/bucket/report.docx"),
        new("requestnumber", "REQ-1"),
        new("bcgovcode", "FIN"),
        new("filename", "report.docx"),
        new("ministryrequestid", "100"),
        new("attributes", "{}"),
        new("batch", "batch-1"),
        new("jobid", "200"),
        new("documentmasterid", "300"),
        new("trigger", "upload"),
        new("createdby", "tester"),
        new("usertoken", "secret")
    };

    [DataTestMethod]
    [DataRow("s3filepath")]
    [DataRow("requestnumber")]
    [DataRow("bcgovcode")]
    [DataRow("filename")]
    [DataRow("ministryrequestid")]
    [DataRow("attributes")]
    [DataRow("batch")]
    [DataRow("jobid")]
    [DataRow("documentmasterid")]
    [DataRow("trigger")]
    [DataRow("createdby")]
    [DataRow("usertoken")]
    public void MissingRequiredFieldIsRejected(string missingField)
    {
        var message = ValidMessageExcept(missingField);

        var error = Assert.ThrowsException<MissingFieldException>(() =>
            FileConversionMessageHandler.ValidateMessage(message));

        StringAssert.Contains(error.Message, missingField);
    }

    [TestMethod]
    public void CompleteMessagePassesValidation()
    {
        FileConversionMessageHandler.ValidateMessage(ValidMessageExcept(null));
    }

    [TestMethod]
    public async Task ReclaimedFailedConversionInvokesConverterAgain()
    {
        var converter = new AlwaysFailingConverter();
        var handler = new FileConversionMessageHandler(
            null!,
            "conversion-stream",
            "dedupe-stream",
            () => new IdempotentConversionDatabase(),
            () => converter);
        var message = ValidMessageExcept(null);
        var redis = new FakeRedisStreamClient
        {
            DeliveryCount = 1,
            AutoClaimResult = new AutoClaimPage(
                "0-0",
                [message],
                Array.Empty<RedisValue>())
        };
        var consumer = new RedisStreamConsumer(
            redis,
            handler,
            "conversion-stream",
            "conversion-group",
            "consumer-1",
            new RedisConsumerSettings(
                TimeSpan.Zero,
                TimeSpan.FromSeconds(1),
                3,
                "conversion-stream:dlq",
                100),
            TimeProvider.System);

        await consumer.ProcessEntryAsync(message, reclaimed: false, default);
        redis.DeliveryCount = 2;
        await consumer.ReclaimOneAsync(default);

        Assert.AreEqual(2, converter.Calls);
        Assert.AreEqual(0, redis.AcknowledgeCalls.Count);
        Assert.AreEqual(0, redis.DeadLetterCalls.Count);
    }

    private static StreamEntry ValidMessageExcept(string? missingField) =>
        new(
            "1-0",
            ValidFields
                .Where(field => field.Name != missingField)
                .ToArray());

    private sealed class IdempotentConversionDatabase : IConversionDatabase
    {
        public Task<S3AccessKeys> getAccessKeyFromDB(string bucket) =>
            Task.FromResult(new S3AccessKeys());

        public Task recordJobStart(StreamEntry message) => Task.CompletedTask;

        public Task<Dictionary<string, Dictionary<string, string>>> recordJobEnd(
            StreamEntry message,
            bool error,
            string jobMessage,
            List<Dictionary<string, string>> attachments) =>
            Task.FromResult(new Dictionary<string, Dictionary<string, string>>());

        public void Dispose()
        {
        }
    }

    private sealed class AlwaysFailingConverter : IFileConverter
    {
        public int Calls { get; private set; }

        public Task<(List<Dictionary<string, string>>, long)> ConvertFile(
            StreamEntry message,
            S3AccessKeys s3AccessKeys)
        {
            Calls++;
            return Task.FromException<(List<Dictionary<string, string>>, long)>(
                new IOException("temporary conversion failure"));
        }

        public void Dispose()
        {
        }
    }
}
