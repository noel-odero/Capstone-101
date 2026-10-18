using Amr.Domain.Enums;

namespace Amr.Application.DTOs.Common;

/// <param name="Definition">The Python service's definition, verbatim as it was returned with the run.</param>
/// <param name="Kind">Cumulative, count, difference or rate. Verified against the evaluator; see Metrics/MetricCatalogue.</param>
/// <param name="Unit">The scale of the value. Simulated quantities only; none is a clinical outcome.</param>
/// <param name="Aggregation">How the value is computed over one episode.</param>
public sealed record MetricDefinitionDto(string Definition, MetricKind Kind, string Unit, string Aggregation);
