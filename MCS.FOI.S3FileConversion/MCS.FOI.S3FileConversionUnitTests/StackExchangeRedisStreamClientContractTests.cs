using MCS.FOI.S3FileConversion.Messaging;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using StackExchange.Redis;

namespace MCS.FOI.S3FileConversionUnitTests;

[TestClass]
public class StackExchangeRedisStreamClientContractTests
{
    [TestMethod]
    public void BuildDlqArgumentsPlacesGroupIdAndMaxLengthBeforeFields()
    {
        var fields = new[]
        {
            new NameValueEntry("reason", "handler_error"),
            new NameValueEntry("delivery_count", "3")
        };

        var args = StackExchangeRedisStreamClient.BuildDlqArguments(
            "file-conversion-group", "1-0", 10_000, fields);

        CollectionAssert.AreEqual(
            new RedisValue[]
            {
                "file-conversion-group", "1-0", 10_000,
                "reason", "handler_error", "delivery_count", "3"
            },
            args);
    }

    [TestMethod]
    public void BuildDlqArgumentsRejectsEmptyFields()
    {
        Assert.ThrowsException<ArgumentException>(() =>
            StackExchangeRedisStreamClient.BuildDlqArguments(
                "file-conversion-group",
                "1-0",
                10_000,
                Array.Empty<NameValueEntry>()));
    }
}
