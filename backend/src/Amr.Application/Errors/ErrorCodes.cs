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
    public const string DatabaseMigrationsPending = "database_migrations_pending";
    public const string PersistenceFailed = "persistence_failed";
    public const string ComparisonContractViolation = "comparison_contract_violation";
    public const string InternalError = "internal_error";
    public const string AuthenticationRequired = "authentication_required";
    public const string AccessDenied = "access_denied";
    public const string CsrfValidationFailed = "csrf_validation_failed";
    public const string InvalidCredentials = "invalid_credentials";
    public const string TooManyAttempts = "too_many_attempts";
    public const string EmailAlreadyRegistered = "email_already_registered";
}
