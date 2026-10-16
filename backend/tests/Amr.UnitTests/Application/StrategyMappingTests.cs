using Amr.Application.Errors;
using Amr.Application.Mappings;
using Amr.Application.PythonContracts;
using Amr.Domain.Enums;

namespace Amr.UnitTests.Application;

public class StrategyMappingTests
{
    [Fact]
    public void The_public_baseline_maps_to_pythons_greedy_and_ppo_to_ppo()
    {
        Assert.Equal("ppo", StrategyMapping.ToPythonId(StrategyKind.Ppo));
        Assert.Equal("greedy", StrategyMapping.ToPythonId(StrategyKind.RandomSusceptibleBaseline));
    }

    [Fact]
    public void Every_public_strategy_has_a_distinct_python_id_that_maps_back()
    {
        var ids = Enum.GetValues<StrategyKind>().Select(StrategyMapping.ToPythonId).ToArray();

        Assert.Equal(ids.Length, ids.Distinct().Count());
        Assert.All(Enum.GetValues<StrategyKind>(), strategy => Assert.Equal(strategy, StrategyMapping.FromPythonId(StrategyMapping.ToPythonId(strategy))));
    }

    [Fact]
    public void The_python_ids_are_the_wire_constants()
    {
        Assert.Equal(
            new[] { PythonStrategyIds.Ppo, PythonStrategyIds.Greedy }.Order(),
            Enum.GetValues<StrategyKind>().Select(StrategyMapping.ToPythonId).Order());
    }

    [Fact]
    public void An_unknown_python_id_is_an_upstream_contract_failure()
    {
        var error = Assert.Throws<AmrException>(() => StrategyMapping.FromPythonId("value_iteration"));

        Assert.Equal((ErrorCategory.UpstreamFailure, ErrorCodes.PythonServiceInvalidResponse), (error.Category, error.Code));
    }

    [Fact]
    public void An_undefined_public_strategy_fails_loudly()
    {
        Assert.Throws<ArgumentOutOfRangeException>(() => StrategyMapping.ToPythonId((StrategyKind)99));
    }

    [Fact]
    public void Both_python_ids_are_accepted_by_the_python_services_request_schema()
    {
        var schema = File.ReadAllText(Path.Combine(RepositoryRoot(), "service", "schemas.py"));

        Assert.Contains($"Literal[\"{PythonStrategyIds.Ppo}\", \"{PythonStrategyIds.Greedy}\"]", schema, StringComparison.Ordinal);
    }

    private static string RepositoryRoot()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);
        while (directory is not null && !File.Exists(Path.Combine(directory.FullName, "Amr.sln")))
        {
            directory = directory.Parent;
        }

        return directory?.Parent?.FullName ?? throw new InvalidOperationException("Repository root not found.");
    }
}
