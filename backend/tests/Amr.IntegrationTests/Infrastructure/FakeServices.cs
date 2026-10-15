using Amr.Application.DTOs.Antibiotics;
using Amr.Application.DTOs.Comparisons;
using Amr.Application.DTOs.Common;
using Amr.Application.DTOs.Health;
using Amr.Application.DTOs.Model;
using Amr.Application.DTOs.Profiles;
using Amr.Application.DTOs.Recommendations;
using Amr.Application.DTOs.Simulations;
using Amr.Application.Interfaces.Services;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;

namespace Amr.IntegrationTests.Infrastructure;

/// <summary>Fake application services for controller tests: they record how they were called and return what the test supplies.</summary>
internal static class FakeServices
{
    public static IWebHostBuilder Use<TService>(this IWebHostBuilder builder, TService fake)
        where TService : class =>
        builder.ConfigureTestServices(services =>
        {
            services.RemoveAll<TService>();
            services.AddSingleton(fake);
        });

    public static Func<TIn, CancellationToken, Task<TOut>> Unconfigured<TIn, TOut>() =>
        (_, _) => throw new InvalidOperationException("The fake was called without being configured.");
}

internal sealed class FakeSimulationService : ISimulationService
{
    public Func<CreateSimulationRequest, CancellationToken, Task<SimulationDto>> Run { get; set; } = FakeServices.Unconfigured<CreateSimulationRequest, SimulationDto>();

    public Func<Guid, CancellationToken, Task<SimulationDto?>> Get { get; set; } = FakeServices.Unconfigured<Guid, SimulationDto?>();

    public List<CreateSimulationRequest> RunRequests { get; } = [];

    public List<Guid> GetIds { get; } = [];

    public Task<SimulationDto> RunAsync(CreateSimulationRequest request, CancellationToken cancellationToken)
    {
        RunRequests.Add(request);
        return Run(request, cancellationToken);
    }

    public Task<SimulationDto?> GetAsync(Guid id, CancellationToken cancellationToken)
    {
        GetIds.Add(id);
        return Get(id, cancellationToken);
    }
}

internal sealed class FakeComparisonService : IComparisonService
{
    public Func<CreateComparisonRequest, CancellationToken, Task<ComparisonDto>> Run { get; set; } = FakeServices.Unconfigured<CreateComparisonRequest, ComparisonDto>();

    public Func<Guid, CancellationToken, Task<ComparisonDto?>> Get { get; set; } = FakeServices.Unconfigured<Guid, ComparisonDto?>();

    public List<CreateComparisonRequest> RunRequests { get; } = [];

    public Task<ComparisonDto> RunAsync(CreateComparisonRequest request, CancellationToken cancellationToken)
    {
        RunRequests.Add(request);
        return Run(request, cancellationToken);
    }

    public Task<ComparisonDto?> GetAsync(Guid id, CancellationToken cancellationToken) => Get(id, cancellationToken);
}

internal sealed class FakeRecommendationService : IRecommendationService
{
    public Func<Guid, CancellationToken, Task<RecommendationDto?>> Get { get; set; } = FakeServices.Unconfigured<Guid, RecommendationDto?>();

    public Task<RecommendationDto?> GetBySimulationAsync(Guid simulationId, CancellationToken cancellationToken) => Get(simulationId, cancellationToken);
}

internal sealed class FakeRunHistoryService : IRunHistoryService
{
    public Func<RecentRunsQuery, CancellationToken, Task<PagedResultDto<RunSummaryDto>>> Recent { get; set; } = FakeServices.Unconfigured<RecentRunsQuery, PagedResultDto<RunSummaryDto>>();

    public List<RecentRunsQuery> Queries { get; } = [];

    public Task<PagedResultDto<RunSummaryDto>> GetRecentAsync(RecentRunsQuery query, CancellationToken cancellationToken)
    {
        Queries.Add(query);
        return Recent(query, cancellationToken);
    }
}

internal sealed class FakeProfileValidationService : IProfileValidationService
{
    public Func<ValidateProfileRequest, CancellationToken, Task<ProfileValidationDto>> Validate { get; set; } = FakeServices.Unconfigured<ValidateProfileRequest, ProfileValidationDto>();

    public List<ValidateProfileRequest> Requests { get; } = [];

    public Task<ProfileValidationDto> ValidateAsync(ValidateProfileRequest request, CancellationToken cancellationToken)
    {
        Requests.Add(request);
        return Validate(request, cancellationToken);
    }
}

internal sealed class FakeModelInfoService : IModelInfoService
{
    public Func<CancellationToken, Task<ModelInfoDto>> Model { get; set; } = _ => throw new InvalidOperationException("Unconfigured.");

    public Func<CancellationToken, Task<AntibioticCatalogueDto>> Antibiotics { get; set; } = _ => throw new InvalidOperationException("Unconfigured.");

    public Task<ModelInfoDto> GetModelAsync(CancellationToken cancellationToken) => Model(cancellationToken);

    public Task<AntibioticCatalogueDto> GetAntibioticsAsync(CancellationToken cancellationToken) => Antibiotics(cancellationToken);
}

internal sealed class FakeHealthService : IHealthService
{
    public Func<CancellationToken, Task<HealthDto>> Readiness { get; set; } = _ => throw new InvalidOperationException("Unconfigured.");

    public HealthDto Liveness { get; set; } = new(HealthState.Healthy, true, [new ComponentHealthDto(HealthComponents.Api, HealthState.Healthy, null)]);

    public Task<HealthDto> GetHealthAsync(CancellationToken cancellationToken) => Readiness(cancellationToken);

    public HealthDto GetLiveness() => Liveness;
}
