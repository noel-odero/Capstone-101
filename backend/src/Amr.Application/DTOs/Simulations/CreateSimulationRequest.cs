using System.ComponentModel.DataAnnotations;
using Amr.Application.DTOs.Common;
using Amr.Domain.Enums;

namespace Amr.Application.DTOs.Simulations;

public sealed record CreateSimulationRequest : RunRequestBase
{
    /// <summary>Accepted values: ppo, dqn, random_susceptible_baseline.</summary>
    [EnumDataType(typeof(StrategyKind))]
    public required StrategyKind Strategy { get; init; }
}
