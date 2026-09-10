using Microsoft.VisualStudio.TestTools.UnitTesting;

namespace MCS.FOI.S3FileConversionIntegrationTests;

[TestClass]
public sealed class DownstreamReadinessTests
{
    [DataTestMethod]
    [DataRow(0, 1, false)]
    [DataRow(1, 1, false)]
    [DataRow(0, 0, false)]
    [DataRow(1, 0, true)]
    public void RequiresOneDedupeEntryAndAcknowledgedInput(
        int dedupeEntryCount,
        long pendingMessageCount,
        bool expected)
    {
        Assert.AreEqual(
            expected,
            DocxConversionEndToEndTests.IsDownstreamReady(
                dedupeEntryCount,
                pendingMessageCount));
    }
}
