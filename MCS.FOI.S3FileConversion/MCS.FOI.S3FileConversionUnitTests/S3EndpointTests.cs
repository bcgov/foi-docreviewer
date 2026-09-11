using MCS.FOI.S3FileConversion.Utilities;
using Microsoft.VisualStudio.TestTools.UnitTesting;

namespace MCS.FOI.S3FileConversionUnitTests;

[TestClass]
[DoNotParallelize]
public sealed class S3EndpointTests
{
    [DataTestMethod]
    [DataRow("http://seaweedfs:8333", "http://seaweedfs:8333")]
    [DataRow("https://objects.example.test", "https://objects.example.test")]
    [DataRow("objects.example.test", "https://objects.example.test")]
    [DataRow("https://objects.example.test/", "https://objects.example.test")]
    public void Gets3hostNormalizesEndpoint(string configured, string expected)
    {
        var original = Environment.GetEnvironmentVariable("S3_HOST");
        try
        {
            Environment.SetEnvironmentVariable("S3_HOST", configured);
            using var client = new FOIS3ObjectStorageClient("key", "secret");
            Assert.AreEqual(expected, client.gets3host());
        }
        finally
        {
            Environment.SetEnvironmentVariable("S3_HOST", original);
        }
    }
}
