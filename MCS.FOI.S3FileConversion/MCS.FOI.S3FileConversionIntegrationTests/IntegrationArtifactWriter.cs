namespace MCS.FOI.S3FileConversionIntegrationTests;

internal sealed class IntegrationArtifactWriter
{
    private readonly string scenarioDirectory;

    public IntegrationArtifactWriter(string rootDirectory, string scenario)
    {
        var normalizedRoot = Path.GetFullPath(rootDirectory);
        scenarioDirectory = ResolveChildPath(normalizedRoot, [scenario]);
    }

    public static IntegrationArtifactWriter FromEnvironment(string scenario)
    {
        var root = Environment.GetEnvironmentVariable("INTEGRATION_ARTIFACTS_DIRECTORY");
        if (string.IsNullOrWhiteSpace(root))
        {
            root = Path.Combine(
                AppContext.BaseDirectory,
                "TestResults",
                "integration",
                "artifacts");
        }

        return new IntegrationArtifactWriter(root, scenario);
    }

    public void Reset()
    {
        if (Directory.Exists(scenarioDirectory))
        {
            Directory.Delete(scenarioDirectory, recursive: true);
        }

        Directory.CreateDirectory(scenarioDirectory);
    }

    public async Task CopyAsync(string sourcePath, params string[] relativePath)
    {
        await using var source = File.OpenRead(sourcePath);
        await WriteAsync(source, relativePath);
    }

    public async Task WriteAsync(Stream content, params string[] relativePath)
    {
        var destination = ResolveChildPath(scenarioDirectory, relativePath);
        Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
        await using var output = File.Create(destination);
        await content.CopyToAsync(output);
    }

    private static string ResolveChildPath(string parent, IReadOnlyCollection<string> components)
    {
        if (components.Count == 0)
        {
            throw new ArgumentException("At least one path component is required", nameof(components));
        }

        var path = parent;
        foreach (var component in components)
        {
            if (string.IsNullOrWhiteSpace(component) ||
                Path.IsPathRooted(component) ||
                component is "." or ".." ||
                component.Contains(Path.DirectorySeparatorChar) ||
                component.Contains(Path.AltDirectorySeparatorChar) ||
                component.Contains('\\'))
            {
                throw new ArgumentException(
                    $"Invalid artifact path component: {component}",
                    nameof(components));
            }

            path = Path.Combine(path, component);
        }

        var normalizedParent = Path.TrimEndingDirectorySeparator(Path.GetFullPath(parent));
        var normalizedPath = Path.GetFullPath(path);
        var comparison = OperatingSystem.IsWindows()
            ? StringComparison.OrdinalIgnoreCase
            : StringComparison.Ordinal;
        if (!normalizedPath.StartsWith(normalizedParent + Path.DirectorySeparatorChar, comparison))
        {
            throw new ArgumentException("Artifact path must remain below its root", nameof(components));
        }

        return normalizedPath;
    }
}
