using System.Text.Json;
using System.Text.Json.Nodes;
using Amr.Application.DTOs.Common;
using Amr.Application.Errors;
using Amr.Application.Metrics;
using Amr.Domain.Enums;

namespace Amr.UnitTests.Application;

/// <summary>The canonical metric catalogue against the real evaluator output captured in the fixtures.</summary>
public class MetricCatalogueTests
{
    private static Dictionary<string, string> PythonDefinitions(string fixture) =>
        JsonNode.Parse(PythonFixtures.Read(fixture))!["metric_definitions"]!.AsObject().ToDictionary(pair => pair.Key, pair => pair.Value!.GetValue<string>());

    [Fact]
    public void Every_public_metric_has_exactly_one_catalogue_entry_and_nothing_else_does()
    {
        var properties = typeof(StrategyMetricsDto).GetProperties().Select(property => property.Name).Order(StringComparer.Ordinal);

        Assert.Equal(properties, MetricCatalogue.Entries.Select(entry => entry.PublicName).Order(StringComparer.Ordinal));
    }

    [Theory]
    [InlineData("simulate_200_ppo")]
    [InlineData("simulate_200_baseline")]
    [InlineData("simulate_200_terminal")]
    [InlineData("compare_200")]
    public void The_catalogue_python_keys_are_exactly_the_keys_python_defines(string fixture)
    {
        Assert.Equal(
            PythonDefinitions(fixture).Keys.Order(StringComparer.Ordinal),
            MetricCatalogue.Entries.Select(entry => entry.PythonKey).Order(StringComparer.Ordinal));
    }

    [Fact]
    public void Python_keys_are_the_snake_case_form_of_the_public_names()
    {
        Assert.All(MetricCatalogue.Entries, entry => Assert.Equal(JsonNamingPolicy.SnakeCaseLower.ConvertName(entry.PublicName), entry.PythonKey));
    }

    [Fact]
    public void Describe_keeps_each_python_definition_verbatim_and_keys_by_the_public_property_name()
    {
        var python = PythonDefinitions("simulate_200_ppo");

        var described = MetricCatalogue.Describe(python);

        Assert.Equal(MetricCatalogue.Entries.Count, described.Count);
        foreach (var entry in MetricCatalogue.Entries)
        {
            var definition = described[JsonNamingPolicy.CamelCase.ConvertName(entry.PublicName)];
            Assert.Equal(python[entry.PythonKey], definition.Definition);
            Assert.Equal((entry.Kind, entry.Unit, entry.Aggregation), (definition.Kind, definition.Unit, definition.Aggregation));
        }
    }

    [Fact]
    public void Rates_are_proportions_and_no_metric_claims_to_be_an_average_or_percentage()
    {
        var rates = MetricCatalogue.Entries.Where(entry => entry.Kind == MetricKind.Rate).Select(entry => entry.PythonKey);

        Assert.Equal(new[] { "resistance_emergence_rate", "susceptible_action_rate" }, rates.Order(StringComparer.Ordinal));
        Assert.All(MetricCatalogue.Entries.Where(entry => entry.Kind == MetricKind.Rate), entry => Assert.Contains("not a percentage", entry.Unit, StringComparison.Ordinal));
        Assert.DoesNotContain(MetricCatalogue.Entries, entry => entry.Unit.Contains("average", StringComparison.OrdinalIgnoreCase) || entry.Aggregation.Contains("mean", StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public void Cumulative_values_are_the_sum_style_metrics_and_the_difference_is_signed()
    {
        var cumulative = MetricCatalogue.Entries.Where(entry => entry.Kind == MetricKind.Cumulative).Select(entry => entry.PythonKey);

        Assert.Equal(new[] { "cumulative_antibiotic_exposure", "cumulative_resistance_burden", "cumulative_reward" }, cumulative.Order(StringComparer.Ordinal));
        Assert.Equal(MetricKind.Difference, MetricCatalogue.Entries.Single(entry => entry.PythonKey == "change_in_susceptible_count").Kind);
    }

    [Fact]
    public void Every_entry_states_a_unit_and_how_it_is_aggregated()
    {
        Assert.All(MetricCatalogue.Entries, entry =>
        {
            Assert.False(string.IsNullOrWhiteSpace(entry.Unit));
            Assert.False(string.IsNullOrWhiteSpace(entry.Aggregation));
        });
    }

    [Fact]
    public void A_missing_extra_or_empty_definition_is_an_invalid_upstream_response()
    {
        var good = PythonDefinitions("simulate_200_ppo");
        var missing = good.Where(pair => pair.Key != "treatment_steps").ToDictionary();
        var extra = new Dictionary<string, string>(good) { ["brand_new_metric"] = "unverified" };
        var empty = new Dictionary<string, string>(good) { ["treatment_steps"] = " " };

        foreach (var definitions in new[] { missing, extra, empty })
        {
            var error = Assert.Throws<AmrException>(() => MetricCatalogue.Describe(definitions));
            Assert.Equal(ErrorCodes.PythonServiceInvalidResponse, error.Code);
        }
    }
}
