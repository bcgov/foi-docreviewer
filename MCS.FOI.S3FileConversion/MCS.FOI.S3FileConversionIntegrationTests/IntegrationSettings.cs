namespace MCS.FOI.S3FileConversionIntegrationTests;

internal sealed record IntegrationSettings(
    string DatabaseConnectionString,
    string RedisConnectionString,
    string S3Endpoint,
    string S3AccessKey,
    string S3SecretKey,
    string S3Bucket,
    string ConversionStream,
    string DedupeStream,
    string ConsumerGroup)
{
    public static IntegrationSettings FromEnvironment() => new(
        Required("DATABASE_CONNECTION_STRING"),
        Required("REDIS_CONNECTION_STRING"),
        Required("S3_ENDPOINT"),
        Required("S3_ACCESS_KEY"),
        Required("S3_SECRET_KEY"),
        Required("S3_BUCKET"),
        Required("CONVERSION_STREAM"),
        Required("DEDUPE_STREAM"),
        Required("CONSUMER_GROUP"));

    private static string Required(string name)
    {
        var value = Environment.GetEnvironmentVariable(name);
        if (string.IsNullOrWhiteSpace(value))
        {
            throw new InvalidOperationException($"{name} is required");
        }

        return value;
    }
}
