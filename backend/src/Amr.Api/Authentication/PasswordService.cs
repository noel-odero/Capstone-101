using Microsoft.AspNetCore.Identity;
using Microsoft.Extensions.Options;

namespace Amr.Api.Authentication;

/// <summary>Salted, slow password hashing (PBKDF2 through the framework hasher). Passwords are never stored, logged or returned.</summary>
public sealed class PasswordService
{
    private const int Iterations = 210_000;
    private static readonly object Subject = new();

    private readonly PasswordHasher<object> hasher = new(Options.Create(new PasswordHasherOptions { IterationCount = Iterations }));
    private readonly string decoyHash;

    public PasswordService() => decoyHash = hasher.HashPassword(Subject, Guid.NewGuid().ToString("N"));

    public string Hash(string password) => hasher.HashPassword(Subject, password);

    public bool Verify(string hash, string password) =>
        hasher.VerifyHashedPassword(Subject, hash, password) != PasswordVerificationResult.Failed;

    /// <summary>Spends the same time as a real check, so an unknown email is not distinguishable from a wrong password by timing.</summary>
    public void VerifyAgainstDecoy(string password) => hasher.VerifyHashedPassword(Subject, decoyHash, password);
}
