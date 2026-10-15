using Amr.Application.DTOs.Antibiotics;
using Amr.Application.DTOs.Comparisons;
using Amr.Application.DTOs.Model;
using Amr.Application.DTOs.Profiles;
using Amr.Application.DTOs.Simulations;
using Amr.Application.Services;
using Amr.Domain.Enums;

namespace Amr.IntegrationTests.Infrastructure;

/// <summary>Realistic DTOs produced by the real mappings from real Python responses, so controller tests never hand-build a result.</summary>
internal static class SampleDtos
{
    private static readonly int[] Profile = [0, 1, 0, 0, 0, 0, 0];

    private static StubHandler Serving(string fixture) => StubHandler.Returning(() => PythonFixtures.Fixture(fixture));

    public static Task<SimulationDto> Simulation(StrategyKind strategy = StrategyKind.Ppo) =>
        new SimulationService(ClientFactory.Create(Serving(strategy == StrategyKind.Ppo ? "simulate_200_ppo" : "simulate_200_baseline")))
            .RunAsync(new() { ResistanceProfile = Profile, Strategy = strategy, EnvironmentSeed = 100001, PolicySeed = strategy == StrategyKind.Ppo ? null : 900001 }, CancellationToken.None);

    public static Task<SimulationDto> TerminalSimulation() =>
        new SimulationService(ClientFactory.Create(Serving("simulate_200_terminal")))
            .RunAsync(new() { ResistanceProfile = [1, 1, 1, 1, 1, 1, 1], Strategy = StrategyKind.Ppo, EnvironmentSeed = 1 }, CancellationToken.None);

    public static Task<ComparisonDto> Comparison() =>
        new ComparisonService(ClientFactory.Create(Serving("compare_200")))
            .RunAsync(new() { ResistanceProfile = Profile, EnvironmentSeed = 100001, PolicySeed = 900001 }, CancellationToken.None);

    public static Task<ModelInfoDto> Model() => new ModelInfoService(ClientFactory.Create(Serving("model_200"))).GetModelAsync(CancellationToken.None);

    public static Task<AntibioticCatalogueDto> Antibiotics() => new ModelInfoService(ClientFactory.Create(Serving("antibiotics_200"))).GetAntibioticsAsync(CancellationToken.None);

    public static Task<ProfileValidationDto> TerminalProfile() =>
        new ProfileValidationService(ClientFactory.Create(Serving("validate_200_terminal")))
            .ValidateAsync(new() { ResistanceProfile = [1, 1, 1, 1, 1, 1, 1] }, CancellationToken.None);
}
