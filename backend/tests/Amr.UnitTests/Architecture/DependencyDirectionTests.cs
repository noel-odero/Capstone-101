using System.Xml.Linq;

namespace Amr.UnitTests.Architecture;

/// <summary>Reads the project files, so the rules hold even when a reference is not yet used by any code.</summary>
public class DependencyDirectionTests
{
    private static readonly string BackendRoot = FindBackendRoot();

    private static string FindBackendRoot()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);
        while (directory is not null && !File.Exists(Path.Combine(directory.FullName, "Amr.sln")))
        {
            directory = directory.Parent;
        }

        return directory?.FullName ?? throw new InvalidOperationException("Amr.sln was not found above the test output directory.");
    }

    private static XDocument Project(string name) => XDocument.Load(Path.Combine(BackendRoot, "src", name, $"{name}.csproj"));

    private static string[] ProjectReferences(string name) =>
        Project(name).Descendants("ProjectReference")
            .Select(element => Path.GetFileNameWithoutExtension((string)element.Attribute("Include")!))
            .Order()
            .ToArray();

    private static string[] PackageReferences(string name) =>
        Project(name).Descendants("PackageReference").Select(element => (string)element.Attribute("Include")!).Order().ToArray();

    [Fact]
    public void Domain_references_no_project_and_no_package()
    {
        Assert.Empty(ProjectReferences("Amr.Domain"));
        Assert.Empty(PackageReferences("Amr.Domain"));
    }

    [Fact]
    public void Application_references_only_the_domain_and_no_package()
    {
        Assert.Equal(["Amr.Domain"], ProjectReferences("Amr.Application"));
        Assert.Empty(PackageReferences("Amr.Application"));
    }

    [Fact]
    public void Infrastructure_references_only_the_application_layer()
    {
        Assert.Equal(["Amr.Application"], ProjectReferences("Amr.Infrastructure"));
    }

    [Fact]
    public void Api_references_the_application_layer_and_infrastructure_only_for_registration()
    {
        Assert.Equal(["Amr.Application", "Amr.Infrastructure"], ProjectReferences("Amr.Api"));
    }

    [Theory]
    [InlineData("Amr.Domain")]
    [InlineData("Amr.Application")]
    [InlineData("Amr.Api")]
    public void Only_infrastructure_talks_http(string name)
    {
        var sources = Directory.EnumerateFiles(Path.Combine(BackendRoot, "src", name), "*.cs", SearchOption.AllDirectories)
            .Where(path => !path.Contains($"{Path.DirectorySeparatorChar}obj{Path.DirectorySeparatorChar}", StringComparison.Ordinal));

        Assert.DoesNotContain(sources, path =>
        {
            var text = File.ReadAllText(path);
            return text.Contains("HttpClient", StringComparison.Ordinal) || text.Contains("IHttpClientFactory", StringComparison.Ordinal);
        });
    }

    [Theory]
    [InlineData("Amr.Domain")]
    [InlineData("Amr.Application")]
    [InlineData("Amr.Infrastructure")]
    public void Only_the_api_project_uses_the_web_sdk(string name)
    {
        Assert.Equal("Microsoft.NET.Sdk", (string)Project(name).Root!.Attribute("Sdk")!);
    }
}
