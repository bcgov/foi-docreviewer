using Microsoft.VisualStudio.TestTools.UnitTesting;

namespace MCS.FOI.S3FileConversionIntegrationTests;

[TestClass]
public sealed class IntegrationArtifactWriterTests
{
    [TestMethod]
    public async Task WriteAsyncCreatesTheRequestedScenarioHierarchy()
    {
        var root = CreateTemporaryDirectory();
        try
        {
            var writer = new IntegrationArtifactWriter(root, "msg");
            await using var content = new MemoryStream([1, 2, 3]);

            await writer.WriteAsync(
                content,
                "attachments",
                "converted",
                "document-3102-budget.pdf");

            var artifact = Path.Combine(
                root,
                "msg",
                "attachments",
                "converted",
                "document-3102-budget.pdf");
            CollectionAssert.AreEqual(new byte[] { 1, 2, 3 }, await File.ReadAllBytesAsync(artifact));
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    [TestMethod]
    public void ResetRemovesOnlyTheCurrentScenarioArtifacts()
    {
        var root = CreateTemporaryDirectory();
        try
        {
            var staleArtifact = Path.Combine(root, "msg", "converted", "stale.pdf");
            var otherScenarioArtifact = Path.Combine(root, "docx", "converted", "result.pdf");
            Directory.CreateDirectory(Path.GetDirectoryName(staleArtifact)!);
            Directory.CreateDirectory(Path.GetDirectoryName(otherScenarioArtifact)!);
            File.WriteAllText(staleArtifact, "stale");
            File.WriteAllText(otherScenarioArtifact, "keep");

            new IntegrationArtifactWriter(root, "msg").Reset();

            Assert.IsFalse(File.Exists(staleArtifact));
            Assert.IsTrue(File.Exists(otherScenarioArtifact));
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    [TestMethod]
    public void ConstructorRejectsScenarioTraversal()
    {
        var root = CreateTemporaryDirectory();
        try
        {
            Assert.ThrowsException<ArgumentException>(
                () => new IntegrationArtifactWriter(root, ".."));
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    [TestMethod]
    public async Task WriteAsyncRejectsDestinationTraversal()
    {
        var root = CreateTemporaryDirectory();
        try
        {
            var writer = new IntegrationArtifactWriter(root, "msg");
            await using var content = new MemoryStream([1, 2, 3]);

            await Assert.ThrowsExceptionAsync<ArgumentException>(
                () => writer.WriteAsync(content, "..", "outside.pdf"));
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    private static string CreateTemporaryDirectory()
    {
        var path = Path.Combine(Path.GetTempPath(), $"integration-artifacts-{Guid.NewGuid():N}");
        Directory.CreateDirectory(path);
        return path;
    }
}
