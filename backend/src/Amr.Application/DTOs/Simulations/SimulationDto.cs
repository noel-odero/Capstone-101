using Amr.Application.DTOs.Common;
using Amr.Domain.Enums;

namespace Amr.Application.DTOs.Simulations;

/// <param name="Result">Null when the run failed; see <paramref name="Error"/>.</param>
public sealed record SimulationDto(
    Guid Id,
    RunStatus Status,
    DateTimeOffset CreatedAtUtc,
    ModelProvenanceDto Provenance,
    SeedConfigurationDto SeedConfiguration,
    StrategyResultDto? Result,
    RunErrorDto? Error,
    string Disclaimer);
