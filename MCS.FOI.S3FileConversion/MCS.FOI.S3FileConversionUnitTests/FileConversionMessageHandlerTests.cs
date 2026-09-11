using MCS.FOI.S3FileConversion;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using StackExchange.Redis;

namespace MCS.FOI.S3FileConversionUnitTests;

[TestClass]
public class FileConversionMessageHandlerTests
{
    private static readonly NameValueEntry[] ValidFields =
    {
        new("s3filepath", "https://s3.example.test/bucket/report.docx"),
        new("requestnumber", "REQ-1"),
        new("bcgovcode", "FIN"),
        new("filename", "report.docx"),
        new("ministryrequestid", "100"),
        new("attributes", "{}"),
        new("batch", "batch-1"),
        new("jobid", "200"),
        new("documentmasterid", "300"),
        new("trigger", "upload"),
        new("createdby", "tester"),
        new("usertoken", "secret")
    };

    [DataTestMethod]
    [DataRow("s3filepath")]
    [DataRow("requestnumber")]
    [DataRow("bcgovcode")]
    [DataRow("filename")]
    [DataRow("ministryrequestid")]
    [DataRow("attributes")]
    [DataRow("batch")]
    [DataRow("jobid")]
    [DataRow("documentmasterid")]
    [DataRow("trigger")]
    [DataRow("createdby")]
    [DataRow("usertoken")]
    public void MissingRequiredFieldIsRejected(string missingField)
    {
        var message = ValidMessageExcept(missingField);

        var error = Assert.ThrowsException<MissingFieldException>(() =>
            FileConversionMessageHandler.ValidateMessage(message));

        StringAssert.Contains(error.Message, missingField);
    }

    [TestMethod]
    public void CompleteMessagePassesValidation()
    {
        FileConversionMessageHandler.ValidateMessage(ValidMessageExcept(null));
    }

    private static StreamEntry ValidMessageExcept(string? missingField) =>
        new(
            "1-0",
            ValidFields
                .Where(field => field.Name != missingField)
                .ToArray());
}
