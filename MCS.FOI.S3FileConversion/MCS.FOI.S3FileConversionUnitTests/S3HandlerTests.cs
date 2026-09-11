using MCS.FOI.S3FileConversion;
using Microsoft.VisualStudio.TestTools.UnitTesting;

namespace MCS.FOI.S3FileConversionUnitTests;

[TestClass]
public sealed class S3HandlerTests
{
    [TestMethod]
    public void AttachmentKeyIsStableForRedelivery()
    {
        var firstDelivery = S3Handler.GetAttachmentKey(
            "requests/FOI-123/message.msg",
            42,
            1,
            ".xlsx");
        var redelivery = S3Handler.GetAttachmentKey(
            "requests/FOI-123/message.msg",
            42,
            1,
            ".xlsx");
        var nextAttachment = S3Handler.GetAttachmentKey(
            "requests/FOI-123/message.msg",
            42,
            2,
            ".xlsx");

        Assert.AreEqual(firstDelivery, redelivery);
        Assert.AreNotEqual(firstDelivery, nextAttachment);
    }
}
