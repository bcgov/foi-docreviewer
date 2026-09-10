using Microsoft.VisualStudio.TestTools.UnitTesting;

namespace MCS.FOI.S3FileConversionIntegrationTests;

[TestClass]
[DoNotParallelize]
public sealed class IntegrationSettingsTests
{
    private static readonly string[] VariableNames =
    [
        "DATABASE_CONNECTION_STRING",
        "REDIS_CONNECTION_STRING",
        "S3_ENDPOINT",
        "S3_ACCESS_KEY",
        "S3_SECRET_KEY",
        "S3_BUCKET",
        "CONVERSION_STREAM",
        "DEDUPE_STREAM",
        "CONSUMER_GROUP"
    ];

    [TestMethod]
    public void FromEnvironmentRejectsMissingDatabaseConnectionString()
    {
        WithEnvironment(
            values: RequiredValues().Where(pair => pair.Key != "DATABASE_CONNECTION_STRING"),
            assertion: () =>
            {
                var exception = Assert.ThrowsException<InvalidOperationException>(
                    IntegrationSettings.FromEnvironment);
                StringAssert.Contains(exception.Message, "DATABASE_CONNECTION_STRING");
            });
    }

    [TestMethod]
    public void FromEnvironmentLoadsAllRequiredValues()
    {
        WithEnvironment(
            values: RequiredValues(),
            assertion: () =>
            {
                var settings = IntegrationSettings.FromEnvironment();

                Assert.AreEqual("Host=postgres;Database=foi", settings.DatabaseConnectionString);
                Assert.AreEqual("redis:6379,password=redis-test", settings.RedisConnectionString);
                Assert.AreEqual("http://seaweedfs:8333", settings.S3Endpoint);
                Assert.AreEqual("dev", settings.S3AccessKey);
                Assert.AreEqual("dev-secret", settings.S3SecretKey);
                Assert.AreEqual("integration-bucket", settings.S3Bucket);
                Assert.AreEqual("file-conversion-integration", settings.ConversionStream);
                Assert.AreEqual("dedupe-integration", settings.DedupeStream);
                Assert.AreEqual("file-conversion-consumer-group", settings.ConsumerGroup);
            });
    }

    private static Dictionary<string, string> RequiredValues() => new()
    {
        ["DATABASE_CONNECTION_STRING"] = "Host=postgres;Database=foi",
        ["REDIS_CONNECTION_STRING"] = "redis:6379,password=redis-test",
        ["S3_ENDPOINT"] = "http://seaweedfs:8333",
        ["S3_ACCESS_KEY"] = "dev",
        ["S3_SECRET_KEY"] = "dev-secret",
        ["S3_BUCKET"] = "integration-bucket",
        ["CONVERSION_STREAM"] = "file-conversion-integration",
        ["DEDUPE_STREAM"] = "dedupe-integration",
        ["CONSUMER_GROUP"] = "file-conversion-consumer-group"
    };

    private static void WithEnvironment(
        IEnumerable<KeyValuePair<string, string>> values,
        Action assertion)
    {
        var originals = VariableNames.ToDictionary(
            name => name,
            Environment.GetEnvironmentVariable);
        try
        {
            foreach (var name in VariableNames)
            {
                Environment.SetEnvironmentVariable(name, null);
            }

            foreach (var (name, value) in values)
            {
                Environment.SetEnvironmentVariable(name, value);
            }

            assertion();
        }
        finally
        {
            foreach (var (name, value) in originals)
            {
                Environment.SetEnvironmentVariable(name, value);
            }
        }
    }
}
