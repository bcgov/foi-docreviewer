namespace MCS.FOI.S3FileConversion.Messaging;

public sealed record RedisConsumerSettings(
    TimeSpan ClaimMinIdle,
    TimeSpan ClaimInterval,
    int MaxDeliveryAttempts,
    string DlqStreamKey,
    int DlqMaxLength)
{
    public const int ProcessingCeilingMinutes = 120;
    public const int DefaultClaimMinIdleMinutes = 150;
    public const int DefaultClaimIntervalSeconds = 30;
    public const int DefaultMaxDeliveryAttempts = 3;
    public const int DefaultDlqMaxLength = 10_000;

    public static RedisConsumerSettings Load(
        Func<string, string?> getenv,
        string inputStreamKey)
    {
        if (string.IsNullOrWhiteSpace(inputStreamKey))
        {
            throw new InvalidOperationException("REDIS_STREAM_KEY is required");
        }

        var claimMinutes = ReadPositiveInt(
            getenv,
            "FILE_CONVERSION_CLAIM_MIN_IDLE_MINUTES",
            DefaultClaimMinIdleMinutes);
        if (claimMinutes <= ProcessingCeilingMinutes)
        {
            throw new InvalidOperationException(
                "FILE_CONVERSION_CLAIM_MIN_IDLE_MINUTES must be greater than 120");
        }

        var dlqOverride = getenv("FILE_CONVERSION_DLQ_STREAM_KEY");
        var dlqStream = string.IsNullOrWhiteSpace(dlqOverride)
            ? $"{inputStreamKey}:dlq"
            : dlqOverride.Trim();

        return new RedisConsumerSettings(
            TimeSpan.FromMinutes(claimMinutes),
            TimeSpan.FromSeconds(ReadPositiveInt(
                getenv,
                "FILE_CONVERSION_CLAIM_INTERVAL_SECONDS",
                DefaultClaimIntervalSeconds)),
            ReadPositiveInt(
                getenv,
                "FILE_CONVERSION_MAX_DELIVERY_ATTEMPTS",
                DefaultMaxDeliveryAttempts),
            dlqStream,
            ReadPositiveInt(
                getenv,
                "FILE_CONVERSION_DLQ_MAX_LENGTH",
                DefaultDlqMaxLength));
    }

    private static int ReadPositiveInt(
        Func<string, string?> getenv,
        string name,
        int defaultValue)
    {
        var raw = getenv(name);
        if (raw is null)
        {
            return defaultValue;
        }

        if (!int.TryParse(raw, out var parsed) || parsed <= 0)
        {
            throw new InvalidOperationException($"{name} must be a positive integer");
        }

        return parsed;
    }
}
