using System.Reflection;
using Amr.Api.Controllers;
using Amr.Application.Interfaces.Services;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.Routing;

namespace Amr.UnitTests.Architecture;

/// <summary>Controllers translate HTTP to application calls and back. These tests keep them from growing logic, clients or storage.</summary>
public class ControllerArchitectureTests
{
    private static readonly Type[] Controllers = typeof(ApiControllerBase).Assembly.GetTypes()
        .Where(type => type is { IsAbstract: false, IsClass: true } && typeof(ApiControllerBase).IsAssignableFrom(type))
        .OrderBy(type => type.Name, StringComparer.Ordinal)
        .ToArray();

    private static readonly string ControllerDirectory = Path.Combine(FindBackendRoot(), "src", "Amr.Api", "Controllers");

    private static string FindBackendRoot()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);
        while (directory is not null && !File.Exists(Path.Combine(directory.FullName, "Amr.sln")))
        {
            directory = directory.Parent;
        }

        return directory?.FullName ?? throw new InvalidOperationException("Amr.sln was not found above the test output directory.");
    }

    private static IEnumerable<MethodInfo> Actions(Type controller) =>
        controller.GetMethods(BindingFlags.Public | BindingFlags.Instance | BindingFlags.DeclaredOnly)
            .Where(method => method.GetCustomAttributes<HttpMethodAttribute>().Any());

    [Fact]
    public void Controllers_depend_only_on_application_service_interfaces()
    {
        var allowedNamespace = typeof(ISimulationService).Namespace;

        foreach (var controller in Controllers.Where(type => type != typeof(AuthController)))
        {
            var constructor = Assert.Single(controller.GetConstructors());
            Assert.All(constructor.GetParameters(), parameter =>
            {
                Assert.True(parameter.ParameterType.IsInterface, $"{controller.Name} takes {parameter.ParameterType.Name}, which is not an interface.");
                Assert.Equal(allowedNamespace, parameter.ParameterType.Namespace);
            });
            Assert.All(
                controller.GetFields(BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public | BindingFlags.DeclaredOnly),
                field => Assert.True(field.IsDefined(typeof(System.Runtime.CompilerServices.CompilerGeneratedAttribute), false), $"{controller.Name} declares field {field.Name}."));
        }
    }

    [Fact]
    public void The_auth_controller_depends_only_on_authentication_services_and_antiforgery()
    {
        var constructor = Assert.Single(typeof(AuthController).GetConstructors());

        Assert.Equal(
            [typeof(Amr.Api.Authentication.AccountService), typeof(Amr.Api.Authentication.EmailVerificationService), typeof(Microsoft.AspNetCore.Antiforgery.IAntiforgery)],
            constructor.GetParameters().Select(parameter => parameter.ParameterType));
    }

    [Fact]
    public void Every_controller_action_accepts_a_cancellation_token()
    {
        foreach (var controller in Controllers)
        {
            foreach (var action in Actions(controller).Where(method => typeof(Task).IsAssignableFrom(method.ReturnType)))
            {
                Assert.True(
                    action.GetParameters().Any(parameter => parameter.ParameterType == typeof(CancellationToken)),
                    $"{controller.Name}.{action.Name} does not accept a CancellationToken.");
            }
        }
    }

    [Fact]
    public void Controller_sources_never_mention_clients_storage_or_mappings()
    {
        var forbidden = new[]
        {
            "IPythonServiceClient", "PythonContracts", "HttpClient", "System.Net.Http", "DbContext", "EntityFrameworkCore",
            "StrategyMapping", "Mappings", "Amr.Infrastructure", "IMemoryCache", "ConcurrentDictionary", "Dictionary<Guid",
            "IRunRepository", "Persistence", "Entities", "SaveChanges",
        };

        var sources = Directory.EnumerateFiles(ControllerDirectory, "*.cs");

        foreach (var path in sources)
        {
            var text = File.ReadAllText(path);
            Assert.All(forbidden, term => Assert.False(text.Contains(term, StringComparison.Ordinal), $"{Path.GetFileName(path)} mentions {term}."));
        }
    }

    [Fact]
    public void Controllers_hold_no_mutable_state()
    {
        foreach (var path in Directory.EnumerateFiles(ControllerDirectory, "*.cs"))
        {
            var text = File.ReadAllText(path);
            Assert.DoesNotContain("static readonly", text, StringComparison.Ordinal);
            Assert.DoesNotContain("static Dictionary", text, StringComparison.Ordinal);
            Assert.DoesNotContain(" new List<", text, StringComparison.Ordinal);
        }
    }
}
