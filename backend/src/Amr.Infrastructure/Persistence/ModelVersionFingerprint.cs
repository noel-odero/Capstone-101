using System.Security.Cryptography;
using System.Text.Json;
using Amr.Application.DTOs.Common;

namespace Amr.Infrastructure.Persistence;

/// <summary>
/// Identity of a model and simulator configuration. Every field that could change a result is included, with the reward
/// specification's keys sorted so equal configurations always hash equally. The service version is deliberately excluded:
/// a new service build over the same checkpoint and data is the same model version.
/// </summary>
internal static class ModelVersionFingerprint
{
    public static string Compute(ModelProvenanceDto provenance)
    {
        using var stream = new MemoryStream();
        using (var writer = new Utf8JsonWriter(stream))
        {
            writer.WriteStartObject();
            writer.WriteString("modelId", provenance.ModelId);
            writer.WriteString("algorithm", provenance.Algorithm);
            writer.WriteString("checkpointSha256", provenance.CheckpointSha256);
            writer.WriteString("interactionDataSha256", provenance.InteractionDataSha256);
            writer.WriteString("scenarioId", provenance.ScenarioId);
            writer.WriteNumber("horizon", provenance.Horizon);
            writer.WriteString("actionMaskRule", provenance.ActionMaskRule);
            writer.WriteStartObject("rewardSpecification");
            foreach (var (key, value) in provenance.RewardSpecification.OrderBy(pair => pair.Key, StringComparer.Ordinal))
            {
                writer.WritePropertyName(key);
                value.WriteTo(writer);
            }

            writer.WriteEndObject();
            writer.WriteStartArray("antibioticOrder");
            foreach (var antibiotic in provenance.AntibioticOrder)
            {
                writer.WriteStringValue(antibiotic);
            }

            writer.WriteEndArray();
            writer.WriteEndObject();
        }

        return Convert.ToHexStringLower(SHA256.HashData(stream.ToArray()));
    }
}
