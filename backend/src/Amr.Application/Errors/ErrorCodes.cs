namespace Amr.Application.Errors;

/// <summary>Stable, public error codes. Clients may branch on these; do not rename.</summary>
public static class ErrorCodes
{
    public const string ValidationFailed = "validation_failed";
    public const string NotFound = "not_found";
    public const string RecommendationNotFound = "recommendation_not_found";
    public const string ModelUnavailable = "model_unavailable";
    public const string PythonServiceUnavailable = "python_service_unavailable";
    public const string PythonServiceTimeout = "python_service_timeout";
    public const string PythonServiceInvalidResponse = "python_service_invalid_response";
    public const string DatabaseUnavailable = "database_unavailable";
    public const string ComparisonContractViolation = "comparison_contract_violation";
    public const string InternalError = "internal_error";
}
