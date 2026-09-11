using Microsoft.VisualStudio.TestTools.UnitTesting;

namespace MCS.FOI.S3FileConversionIntegrationTests;

[TestClass]
public sealed class DownstreamReadinessTests
{
    [DataTestMethod]
    [DataRow(0L, 0L, 1L, 0L, false)]
    [DataRow(0L, 1L, 1L, 1L, false)]
    [DataRow(0L, 1L, 1L, 0L, true)]
    [DataRow(0L, 2L, 1L, 0L, false)]
    [DataRow(4L, 4L, 1L, 0L, false)]
    [DataRow(4L, 5L, 1L, 0L, true)]
    [DataRow(1L, 5L, 4L, 0L, true)]
    public void RequiresExpectedNewDedupeEntriesAndNoPendingMessages(
        long baselineDedupeCount,
        long currentDedupeCount,
        long expectedNewDedupeCount,
        long pendingMessageCount,
        bool expected)
    {
        Assert.AreEqual(
            expected,
            DownstreamReadiness.HasSettled(
                baselineDedupeCount,
                currentDedupeCount,
                expectedNewDedupeCount,
                pendingMessageCount));
    }
}
