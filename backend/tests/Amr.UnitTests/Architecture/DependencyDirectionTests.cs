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
            .Select(element => Path.GetFileNameWithoutExtension(((string)element.Attribute("Include")!).Replace('\\', '/')))
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
    public void Only_infrastructure_knows_entity_framework_or_the_database_driver(string name)
    {
        var sources = Directory.EnumerateFiles(Path.Combine(BackendRoot, "src", name), "*.cs", SearchOption.AllDirectories)
            .Where(path => !path.Contains($"{Path.DirectorySeparatorChar}obj{Path.DirectorySeparatorChar}", StringComparison.Ordinal));

        Assert.DoesNotContain(sources, path =>
        {
            var text = File.ReadAllText(path);
            return text.Contains("EntityFrameworkCore", StringComparison.Ordinal) || text.Contains("Npgsql", StringComparison.Ordinal) || text.Contains("DbContext", StringComparison.Ordinal);
        });
    }

    [Fact]
    public void Ef_entities_never_appear_in_the_application_or_api_surface()
    {
        var published = new[] { typeof(Amr.Application.DTOs.Common.StrategyResultDto).Assembly, typeof(Amr.Api.Routing.ApiRoutes).Assembly }
            .SelectMany(assembly => assembly.GetExportedTypes())
            .SelectMany(type => type.GetMethods().Select(method => method.ReturnType).Concat(type.GetProperties().Select(property => property.PropertyType)))
            .Select(type => type.FullName ?? string.Empty);

        Assert.DoesNotContain(published, name => name.Contains("Persistence.Entities", StringComparison.Ordinal));
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
