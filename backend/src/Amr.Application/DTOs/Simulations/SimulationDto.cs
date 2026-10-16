using Amr.Application.DTOs.Common;
using Amr.Domain.Enums;

namespace Amr.Application.DTOs.Simulations;

/// <param name="Id">The scientific service's run id, which is also the stored resource id: GET /simulations/{id} returns this run once IsPersisted is true.</param>
/// <param name="IsPersisted">True only after the run was durably committed; a response is never sent with true before that.</param>
/// <param name="Result">Null when the run failed; see <paramref name="Error"/>. Only completed runs are stored.</param>
/// <param name="MetricDefinitions">Definitions of every metric in the result, keyed by the metric property name and stored with the run.</param>
public sealed record SimulationDto(
    Guid Id,
    RunStatus Status,
    bool IsPersisted,
    DateTimeOffset CreatedAtUtc,
    ModelProvenanceDto Provenance,
    SeedConfigurationDto SeedConfiguration,
    StrategyResultDto? Result,
    RunErrorDto? Error,
    IReadOnlyDictionary<string, MetricDefinitionDto> MetricDefinitions,
    string Disclaimer);
