namespace Amr.Application.Errors;

public static class ComparisonErrors
{
    /// <summary>The paired runs did not satisfy the comparison contract. No result is returned; the Python service raises the same failure.</summary>
    public static AmrException ContractViolation() => new(
        ErrorCategory.Internal,
        ErrorCodes.ComparisonContractViolation,
        "The paired runs did not satisfy the comparison contract; no result was produced.");
}
