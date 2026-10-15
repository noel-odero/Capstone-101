using System.Text.Json;

namespace Amr.Application.PythonContracts;

/// <summary>Error envelope returned by every failing /internal route: {"error": {...}}.</summary>
public sealed record PythonErrorEnvelope(PythonErrorBody Error);

/// <param name="Details">Validation locations or the failed comparison check; omitted by Python when empty.</param>
public sealed record PythonErrorBody(
    string Code,
    string Message,
    string RequestId,
    IReadOnlyList<IReadOnlyDictionary<string, JsonElement>>? Details = null);

/// <summary>Python error codes the client maps; anything else is treated as an unexpected upstream failure.</summary>
public static class PythonErrorCodes
{
    public const string InvalidContext = "invalid_context";
    public const string RequestValidationError = "request_validation_error";
    public const string ModelNotLoaded = "model_not_loaded";
    public const string CheckpointIntegrityFailure = "checkpoint_integrity_failure";
    public const string ModelContractMismatch = "model_contract_mismatch";
    public const string ModelOrDataUnavailable = "model_or_data_unavailable";
    public const string ComparisonContractViolation = "comparison_contract_violation";
}
