using System.ComponentModel.DataAnnotations;
using System.Text.Json;
using Amr.Application.DTOs.Analyses;
using Amr.Application.DTOs.Common;
using Amr.Application.Errors;
using Amr.Application.Interfaces.Persistence;
using Amr.Application.Interfaces.Services;
using Amr.Domain.Enums;

namespace Amr.Application.Services;

/// <summary>Describes saved evaluations. It has no scientific-service client and never executes a policy.</summary>
public sealed class AnalysisComparisonService(IAnalysisRepository repository) : IAnalysisComparisonService
{
    public async Task<AnalysisComparisonDto> CompareAsync(CompareAnalysesRequest request, CancellationToken cancellationToken)
    {
        Validator.ValidateObject(request, new ValidationContext(request), validateAllProperties: true);
        var found = await repository.FindManyAsync(request.AnalysisIds, cancellationToken);
        var byId = found.ToDictionary(run => run.Id);
        if (request.AnalysisIds.Any(id => !byId.ContainsKey(id)))
            throw new AmrException(ErrorCategory.NotFound, "analysis_not_found", "One or more selected analyses are unavailable. Choose saved records in Analysis Insights.");

        var analyses = request.AnalysisIds.Select(id => byId[id]).ToArray();
        var differences = analyses.Select(run =>
        {
            double? Burden(StrategyKind strategy) => run.Strategies.FirstOrDefault(result => result.Strategy == strategy)?.Metrics.CumulativeResistanceBurden;
            return new PolicyBurdenDifferencesDto(run.Id, Burden(StrategyKind.Ppo) - Burden(StrategyKind.Dqn),
                Burden(StrategyKind.Ppo) - Burden(StrategyKind.RandomSusceptibleBaseline),
                Burden(StrategyKind.Dqn) - Burden(StrategyKind.RandomSusceptibleBaseline));
        }).ToArray();
        return new AnalysisComparisonDto(analyses, CheckCompatibility(analyses), differences,
            "Descriptive comparison of user-selected saved analyses. No policies were rerun. Matching recorded settings do not establish a controlled sample, statistical independence, clinical validity or overall algorithm superiority. No pooled performance statistic is calculated.");
    }

    internal static AnalysisCompatibilityDto CheckCompatibility(IReadOnlyList<SavedAnalysisDto> analyses)
    {
        var issues = new List<CompatibilityIssueDto>();
        var ids = analyses.Select(run => run.Id).ToArray();
        void Different(string code, string message, Func<SavedAnalysisDto, string> key, string severity = "incompatible")
        {
            if (analyses.Select(key).Distinct(StringComparer.Ordinal).Skip(1).Any())
                issues.Add(new(code, severity, message, ids));
        }
        void Missing(string code, string message, Func<SavedAnalysisDto, bool> predicate, string severity = "incompatible")
        {
            var affected = analyses.Where(predicate).Select(run => run.Id).ToArray();
            if (affected.Length > 0) issues.Add(new(code, severity, message, affected));
        }
        Missing("provenance_unknown", "Some scientific identity fields are unavailable; compatibility cannot be verified.", run =>
            !HashKnown(run.Provenance.InteractionDataSha256) || string.IsNullOrWhiteSpace(run.Provenance.ScenarioId) ||
            string.IsNullOrWhiteSpace(run.Provenance.ActionMaskRule) || run.Provenance.Horizon <= 0 ||
            run.Provenance.AntibioticOrder.Count != 7 || run.Provenance.AntibioticOrder.Any(string.IsNullOrWhiteSpace) ||
            run.Provenance.AntibioticOrder.Distinct(StringComparer.OrdinalIgnoreCase).Count() != 7 ||
            run.Provenance.RewardSpecification.Count == 0 || string.IsNullOrWhiteSpace(run.Provenance.ServiceVersion));
        Different("environment_changed", "Transition data or scenario differs between these analyses.", run => Canonical(new { run.Provenance.InteractionDataSha256, run.Provenance.ScenarioId }));
        Different("evaluation_changed", "Horizon, action mapping, action mask or reward definition differs.", run => Canonical(new { run.Provenance.Horizon, run.Provenance.AntibioticOrder, run.Provenance.ActionMaskRule, run.Provenance.RewardSpecification }));
        var metricKeys = new[] { "cumulativeResistanceBurden", "resistanceEmergenceEvents", "finalSusceptibleCount", "unsupportedStepCount" };
        Missing("metric_definition_unknown", "A displayed metric has no recorded definition.", run => metricKeys.Any(key => !run.MetricDefinitions.ContainsKey(key)));
        Different("metric_definitions_changed", "Stored metric definitions differ. Values are shown individually without pooling.", run => Canonical(metricKeys.ToDictionary(key => key, key => run.MetricDefinitions.GetValueOrDefault(key))));
        Missing("pairing_unverified", "Shared strategy conditions were not verified for some saved comparisons.", run => run.Kind == ExperimentKind.Comparison && run.ComparisonVerified != true);

        foreach (var strategy in new[] { StrategyKind.Ppo, StrategyKind.Dqn })
        {
            var label = strategy == StrategyKind.Ppo ? "PPO" : "DQN";
            var available = analyses.Where(run => run.Strategies.Any(result => result.Strategy == strategy)).ToArray();
            Missing($"{strategy.ToString().ToLowerInvariant()}_unavailable", $"{label} is unavailable in some saved analyses; missing results are not zero.",
                run => !run.Strategies.Any(result => result.Strategy == strategy), "availability");
            var unknown = available.Where(run => Identity(run, strategy) is not { } model || !HashKnown(model.CheckpointSha256)).Select(run => run.Id).ToArray();
            if (unknown.Length > 0) issues.Add(new("checkpoint_unknown", "incompatible", $"Some {label} checkpoint identities are unavailable.", unknown));
            if (available.Select(run => Canonical(Identity(run, strategy))).Distinct(StringComparer.Ordinal).Skip(1).Any())
                issues.Add(new("checkpoint_changed", "incompatible", $"Different {label} checkpoints were used.", available.Select(run => run.Id).ToArray()));
        }
        Missing("baseline_unavailable", "The random susceptible baseline is unavailable in some saved analyses.",
            run => !run.Strategies.Any(result => result.Strategy == StrategyKind.RandomSusceptibleBaseline), "availability");
        Different("service_version_changed", "Scientific-service versions differ; execution equivalence is not established.", run => run.Provenance.ServiceVersion, "exploratory");
        Different("different_initial_profiles", "Starting profiles differ. Differences describe these chosen starting conditions, not overall policy superiority.", run => string.Join("", run.InitialProfile), "exploratory");
        Different("different_seeds", "Stochastic seeds differ. These records are separate observations, not a verified controlled evaluation batch.", run => Canonical(new { run.SeedConfiguration.EnvironmentSeed, run.SeedConfiguration.PolicySeed }), "exploratory");
        var repeated = analyses.GroupBy(run => Canonical(new { run.InitialProfile, run.SeedConfiguration.EnvironmentSeed, run.SeedConfiguration.PolicySeed, run.Provenance, Models = run.Strategies.Select(result => result.Model).ToArray() }))
            .Where(group => group.Count() > 1).SelectMany(group => group.Select(run => run.Id)).ToArray();
        if (repeated.Length > 0) issues.Add(new("shared_random_draws", "exploratory", "Some analyses reuse the same recorded profile, seeds and configuration. They are not independent extra samples.", repeated));
        var status = issues.Any(issue => issue.Severity == "incompatible") ? "incompatible" : issues.Count > 0 ? "exploratory" : "compatible";
        return new(status, issues);
    }

    private static bool HashKnown(string value) => value.Length == 64 && value.All(Uri.IsHexDigit);

    private static PolicyModelDto? Identity(SavedAnalysisDto run, StrategyKind strategy)
    {
        var result = run.Strategies.First(item => item.Strategy == strategy);
        if (result.Model is not null) return result.Model;
        var expected = strategy == StrategyKind.Ppo ? "MaskablePPO" : "MaskedDQN";
        return run.Provenance.Algorithm == expected
            ? new(run.Provenance.ModelId, run.Provenance.Algorithm, run.Provenance.CheckpointSha256) : null;
    }

    private static string Canonical(object? value)
    {
        static object? Normalize(JsonElement element) => element.ValueKind switch
        {
            JsonValueKind.Object => element.EnumerateObject().OrderBy(property => property.Name, StringComparer.Ordinal)
                .ToDictionary(property => property.Name, property => Normalize(property.Value)),
            JsonValueKind.Array => element.EnumerateArray().Select(Normalize).ToArray(),
            _ => element.Clone(),
        };
        return JsonSerializer.Serialize(Normalize(JsonSerializer.SerializeToElement(value)));
    }
}
