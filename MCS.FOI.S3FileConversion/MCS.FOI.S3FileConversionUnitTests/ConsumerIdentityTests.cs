using MCS.FOI.S3FileConversion.Utilities;
using Microsoft.VisualStudio.TestTools.UnitTesting;

namespace MCS.FOI.S3FileConversionUnitTests
{
    [TestClass]
    public class ConsumerIdentityTests
    {
        [DataTestMethod]
        [DataRow("reviewer-conversion-abc-123", "reviewer-conversion-abc-123")]
        [DataRow("  reviewer-conversion-abc-123 \t", "reviewer-conversion-abc-123")]
        [DataRow("reviewer-conversion-largefiles-xyz", "reviewer-conversion-largefiles-xyz")]
        public void ResolveUsesTrimmedConsumerName(string input, string expected)
        {
            var result = ConsumerIdentity.Resolve(input, "local-host", 42);
            Assert.AreEqual(expected, result.Name);
            Assert.IsFalse(result.IsFallback);
        }

        [DataTestMethod]
        [DataRow(null)]
        [DataRow("")]
        [DataRow(" \t\r\n")]
        public void ResolveFallsBackForMissingConsumerName(string? input)
        {
            var result = ConsumerIdentity.Resolve(input, "local-host", 42);
            Assert.AreEqual("local-host-42", result.Name);
            Assert.IsTrue(result.IsFallback);
        }

        [TestMethod]
        public void ResolveDistinguishesLocalProcesses()
        {
            var first = ConsumerIdentity.Resolve(null, "local-host", 42);
            var second = ConsumerIdentity.Resolve(null, "local-host", 43);
            Assert.AreNotEqual(first.Name, second.Name);
        }

        [TestMethod]
        public void ResolveKeepsConsumerNameAcrossProcessRestarts()
        {
            var first = ConsumerIdentity.Resolve("pod-one", "host", 42);
            var second = ConsumerIdentity.Resolve("pod-one", "host", 43);
            Assert.AreEqual(first.Name, second.Name);
        }
    }
}
