using System.Globalization;
using System.Reflection;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using MsgReader.Outlook;
using OpenMcdf;

namespace MCS.FOI.MSGToPDF.UnitTests;

[TestClass]
public class MessageDateFormatterTests
{
    [DataTestMethod]
    [DataRow("2025-01-15T20:00:00Z", "2025-01-15T12:00:00")]
    [DataRow("2026-01-15T20:00:00Z", "2026-01-15T12:00:00")]
    [DataRow("2026-03-08T09:59:59Z", "2026-03-08T01:59:59")]
    [DataRow("2026-03-08T10:00:00Z", "2026-03-08T03:00:00")]
    [DataRow("2026-11-01T08:59:59Z", "2026-11-01T01:59:59")]
    [DataRow("2026-11-01T09:00:00Z", "2026-11-01T02:00:00")]
    [DataRow("2026-11-03T07:30:00Z", "2026-11-03T00:30:00")]
    [DataRow("2026-11-02T23:31:00Z", "2026-11-02T16:31:00")]
    [DataRow("2027-01-15T19:00:00Z", "2027-01-15T12:00:00")]
    public void SentHeader_UsesVancouverRulesForUtcAndHostLocalValues(string source, string expected)
    {
        var utc = DateTime.Parse(source, CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind);
        var expectedText = DateTime.Parse(expected, CultureInfo.InvariantCulture) + " Pacific Time";

        Assert.AreEqual(expectedText, MessageDateFormatter.FormatSentOn(utc, null));
        // MsgReader 4.5 returns the same instant with Kind=Local (FromFileTime).
        Assert.AreEqual(expectedText, MessageDateFormatter.FormatSentOn(utc.ToLocalTime(), null));
    }

    [DataTestMethod]
    [DataRow("2026-11-03T03:30:00-04:00")]
    [DataRow("2026-11-03T13:00:00+05:30")]
    [DataRow("2026-11-02T23:30:00-08:00")]
    public void SentHeader_PreservesNonBcSourceInstant(string source)
    {
        var instant = DateTimeOffset.Parse(source, CultureInfo.InvariantCulture);
        var expected = new DateTime(2026, 11, 3, 0, 30, 0) + " Pacific Time";
        Assert.AreEqual(expected, MessageDateFormatter.FormatSentOn(instant.UtcDateTime, null));
    }

    [TestMethod]
    public void SentHeader_UsesCreationTimeOnlyWhenSentTimeIsMissing()
    {
        var created = new DateTime(2026, 11, 3, 7, 30, 0, DateTimeKind.Utc);
        var expected = new DateTime(2026, 11, 3, 0, 30, 0) + " Pacific Time";
        Assert.AreEqual(expected, MessageDateFormatter.FormatSentOn(null, created));
        Assert.AreEqual(expected, MessageDateFormatter.FormatSentOn(DateTime.MinValue, created));

        var sent = new DateTime(2025, 1, 15, 20, 0, 0, DateTimeKind.Utc);
        Assert.AreEqual(new DateTime(2025, 1, 15, 12, 0, 0) + " Pacific Time",
            MessageDateFormatter.FormatSentOn(sent, created));
    }

    [TestMethod]
    public void SentHeader_DoesNotInventAnInstantWhenTimestampIsUnknown()
    {
        Assert.AreEqual("Unknown", MessageDateFormatter.FormatSentOn(null, null));
        Assert.AreEqual("Unknown", MessageDateFormatter.FormatSentOn(DateTime.MinValue, DateTime.MinValue));
        Assert.AreEqual("Unknown", MessageDateFormatter.FormatSentOn(new DateTime(2026, 11, 3, 7, 30, 0), null));
    }

    [DataTestMethod]
    [DataRow("2025-01-15T20:00:00Z", "2025-01-15T12:00:00")]
    [DataRow("2026-11-03T07:30:00Z", "2026-11-03T00:30:00")]
    public void ActualMsgHeader_ConvertsMapiFileTimeBeforePdfRendering(string source, string expected)
    {
        var instant = DateTime.Parse(source, CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind);
        var fixture = Path.Combine(AppContext.BaseDirectory, "SourceFiles", "simple-test-msg-file.msg");
        using var original = new MemoryStream(File.ReadAllBytes(fixture));
        using var compound = new CompoundFile(original);
        var properties = compound.RootStorage.GetStream("__properties_version1.0");
        var data = properties.GetData();
        var found = false;
        // Top-level MSG property streams have a 32-byte header, then 16-byte properties.
        for (var offset = 32; offset + 16 <= data.Length; offset += 16)
        {
            if (BitConverter.ToUInt16(data, offset) == 0x0040 &&
                BitConverter.ToUInt16(data, offset + 2) == 0x0039)
            {
                BitConverter.GetBytes(instant.ToFileTimeUtc()).CopyTo(data, offset + 8);
                found = true;
            }
        }
        Assert.IsTrue(found, "MSG fixture must include PR_CLIENT_SUBMIT_TIME.");
        properties.SetData(data);
        using var modified = new MemoryStream();
        compound.Save(modified);
        modified.Position = 0;
        using var message = new Storage.Message(modified);
        Assert.AreEqual(instant, message.SentOn!.Value.ToUniversalTime());

        using var processor = new MSGFileProcessor();
        var generateHtml = typeof(MSGFileProcessor).GetMethod("GenerateHtmlfromMsg",
            BindingFlags.Instance | BindingFlags.NonPublic)!;
        var html = (string)generateHtml.Invoke(processor, new object[] { message })!;
        StringAssert.Contains(html, DateTime.Parse(expected, CultureInfo.InvariantCulture) + " Pacific Time");
    }
}
