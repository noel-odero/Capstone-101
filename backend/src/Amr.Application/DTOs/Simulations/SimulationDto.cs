using Amr.Application.DTOs.Common;
using Amr.Domain.Enums;

namespace Amr.Application.DTOs.Simulations;

/// <param name="Id">The scientific service's run id. Until persistence exists it identifies this execution only and cannot be retrieved.</param>
/// <param name="IsPersisted">False when the run is not stored, so GET by id does not work for it.</param>
/// <param name="Result">Null when the run failed; see <paramref name="Error"/>.</param>
public sealed record SimulationDto(
    Guid Id,
    RunStatus Status,
    bool IsPersisted,
    DateTimeOffset CreatedAtUtc,
    ModelProvenanceDto Provenance,
    SeedConfigurationDto SeedConfiguration,
    StrategyResultDto? Result,
    RunErrorDto? Error,
    string Disclaimer);
