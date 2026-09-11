using System.Text.RegularExpressions;
using Microsoft.VisualStudio.TestTools.UnitTesting;

namespace MCS.FOI.S3FileConversionUnitTests;

[TestClass]
public sealed class DeploymentRecoveryConfigurationTests
{
    private static readonly string[] RecoveryVariables =
    [
        "FILE_CONVERSION_CLAIM_MIN_IDLE_MINUTES",
        "FILE_CONVERSION_CLAIM_INTERVAL_SECONDS",
        "FILE_CONVERSION_MAX_DELIVERY_ATTEMPTS",
        "FILE_CONVERSION_DLQ_STREAM_KEY",
        "FILE_CONVERSION_DLQ_MAX_LENGTH"
    ];

    [TestMethod]
    public void RootComposeForwardsEveryRecoveryVariable()
    {
        var compose = ReadRepositoryFile("docker-compose.yml");

        foreach (var variable in RecoveryVariables)
        {
            StringAssert.Contains(compose, $"- {variable}=${{{variable}}}");
        }
    }

    [TestMethod]
    public void IntegrationComposePinsRecoveryDefaults()
    {
        var compose = ReadRepositoryFile(
            "MCS.FOI.S3FileConversion/docker-compose.integration.yml");
        var expected = new Dictionary<string, string>
        {
            ["FILE_CONVERSION_CLAIM_MIN_IDLE_MINUTES"] = "150",
            ["FILE_CONVERSION_CLAIM_INTERVAL_SECONDS"] = "30",
            ["FILE_CONVERSION_MAX_DELIVERY_ATTEMPTS"] = "3",
            ["FILE_CONVERSION_DLQ_STREAM_KEY"] = string.Empty,
            ["FILE_CONVERSION_DLQ_MAX_LENGTH"] = "10000"
        };

        foreach (var (variable, value) in expected)
        {
            StringAssert.Matches(
                compose,
                new Regex(
                    $"^\\s+{Regex.Escape(variable)}:\\s*\\\"{Regex.Escape(value)}\\\"\\s*$",
                    RegexOptions.Multiline));
        }
    }

    [DataTestMethod]
    [DataRow("openshift/templates/fileconv-deploy.yaml")]
    [DataRow("openshift/templates/fileconv-largefiles-deploy.yaml")]
    public void OpenShiftTemplateDeclaresAndMapsEveryRecoveryVariable(string path)
    {
        var template = ReadRepositoryFile(path);

        foreach (var variable in RecoveryVariables)
        {
            Assert.AreEqual(
                1,
                Regex.Matches(
                    template,
                    $"^\\s+- name: {Regex.Escape(variable)}\\s*$",
                    RegexOptions.Multiline).Count,
                $"Expected exactly one container environment mapping for {variable} in {path}.");
            Assert.AreEqual(
                1,
                Regex.Matches(
                    template,
                    $"^- name: {Regex.Escape(variable)}\\s*$",
                    RegexOptions.Multiline).Count,
                $"Expected exactly one parameter declaration for {variable} in {path}.");
            StringAssert.Contains(template, $"value: \"${{{variable}}}\"");
        }
    }

    private static string ReadRepositoryFile(string relativePath)
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);

        while (directory is not null)
        {
            var path = Path.Combine(directory.FullName, relativePath);
            if (File.Exists(path))
            {
                return File.ReadAllText(path);
            }

            directory = directory.Parent;
        }

        Assert.Fail($"Could not find repository file {relativePath} from {AppContext.BaseDirectory}.");
        return string.Empty;
    }
}
