namespace Amr.Domain.Enums;

/// <summary>Public strategy identifiers. The baseline wraps the Python GreedyPolicy, which samples uniformly among susceptible actions.</summary>
public enum StrategyKind
{
    Ppo,
    RandomSusceptibleBaseline,
}
