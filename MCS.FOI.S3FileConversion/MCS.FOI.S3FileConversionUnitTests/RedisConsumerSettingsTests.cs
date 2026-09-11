using MCS.FOI.S3FileConversion.Messaging;
using Microsoft.VisualStudio.TestTools.UnitTesting;

namespace MCS.FOI.S3FileConversionUnitTests;

[TestClass]
public class RedisConsumerSettingsTests
{
    [TestMethod]
    public void LoadUsesRecoveryDefaultsAndDerivedDlqName()
    {
        var settings = RedisConsumerSettings.Load(EnvironmentWith(), "file-conversion");

        Assert.AreEqual(TimeSpan.FromMinutes(150), settings.ClaimMinIdle);
        Assert.AreEqual(TimeSpan.FromSeconds(30), settings.ClaimInterval);
        Assert.AreEqual(3, settings.MaxDeliveryAttempts);
        Assert.AreEqual("file-conversion:dlq", settings.DlqStreamKey);
        Assert.AreEqual(10_000, settings.DlqMaxLength);
    }

    [DataTestMethod]
    [DataRow(null)]
    [DataRow("")]
    [DataRow("   ")]
    public void LoadUsesDerivedDlqNameWhenOverrideIsBlank(string? value)
    {
        var settings = RedisConsumerSettings.Load(
            EnvironmentWith(("FILE_CONVERSION_DLQ_STREAM_KEY", value)),
            "file-conversion-large");

        Assert.AreEqual("file-conversion-large:dlq", settings.DlqStreamKey);
    }

    [TestMethod]
    public void LoadUsesAllValidOverrides()
    {
        var settings = RedisConsumerSettings.Load(
            EnvironmentWith(
                ("FILE_CONVERSION_CLAIM_MIN_IDLE_MINUTES", "121"),
                ("FILE_CONVERSION_CLAIM_INTERVAL_SECONDS", "15"),
                ("FILE_CONVERSION_MAX_DELIVERY_ATTEMPTS", "5"),
                ("FILE_CONVERSION_DLQ_STREAM_KEY", " custom-dlq "),
                ("FILE_CONVERSION_DLQ_MAX_LENGTH", "2500")),
            "file-conversion");

        Assert.AreEqual(TimeSpan.FromMinutes(121), settings.ClaimMinIdle);
        Assert.AreEqual(TimeSpan.FromSeconds(15), settings.ClaimInterval);
        Assert.AreEqual(5, settings.MaxDeliveryAttempts);
        Assert.AreEqual("custom-dlq", settings.DlqStreamKey);
        Assert.AreEqual(2_500, settings.DlqMaxLength);
    }

    [DataTestMethod]
    [DataRow("120")]
    [DataRow("0")]
    [DataRow("-1")]
    [DataRow("not-a-number")]
    public void LoadRejectsUnsafeClaimMinimumIdle(string value)
    {
        AssertInvalidValue("FILE_CONVERSION_CLAIM_MIN_IDLE_MINUTES", value);
    }

    [DataTestMethod]
    [DataRow("0")]
    [DataRow("-1")]
    [DataRow("not-a-number")]
    public void LoadRejectsInvalidClaimInterval(string value)
    {
        AssertInvalidValue("FILE_CONVERSION_CLAIM_INTERVAL_SECONDS", value);
    }

    [DataTestMethod]
    [DataRow("0")]
    [DataRow("-1")]
    [DataRow("not-a-number")]
    public void LoadRejectsInvalidMaxDeliveryAttempts(string value)
    {
        AssertInvalidValue("FILE_CONVERSION_MAX_DELIVERY_ATTEMPTS", value);
    }

    [DataTestMethod]
    [DataRow("0")]
    [DataRow("-1")]
    [DataRow("not-a-number")]
    public void LoadRejectsInvalidDlqMaxLength(string value)
    {
        AssertInvalidValue("FILE_CONVERSION_DLQ_MAX_LENGTH", value);
    }

    [DataTestMethod]
    [DataRow("")]
    [DataRow("   ")]
    public void LoadRejectsBlankInputStreamKey(string inputStreamKey)
    {
        var error = Assert.ThrowsException<InvalidOperationException>(() =>
            RedisConsumerSettings.Load(EnvironmentWith(), inputStreamKey));

        StringAssert.Contains(error.Message, "REDIS_STREAM_KEY");
    }

    private static void AssertInvalidValue(string name, string value)
    {
        var error = Assert.ThrowsException<InvalidOperationException>(() =>
            RedisConsumerSettings.Load(EnvironmentWith((name, value)), "file-conversion"));

        StringAssert.Contains(error.Message, name);
    }

    private static Func<string, string?> EnvironmentWith(
        params (string Name, string? Value)[] values)
    {
        var environment = values.ToDictionary(item => item.Name, item => item.Value);
        return name => environment.GetValueOrDefault(name);
    }
}
