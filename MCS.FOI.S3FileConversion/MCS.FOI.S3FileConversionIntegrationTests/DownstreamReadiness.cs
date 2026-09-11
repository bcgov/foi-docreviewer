namespace MCS.FOI.S3FileConversionIntegrationTests;

internal static class DownstreamReadiness
{
    internal static bool HasSettled(
        long baselineDedupeCount,
        long currentDedupeCount,
        long expectedNewDedupeCount,
        long pendingMessageCount) =>
        currentDedupeCount == baselineDedupeCount + expectedNewDedupeCount &&
        pendingMessageCount == 0;
}
