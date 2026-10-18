using System.ComponentModel.DataAnnotations;

namespace Amr.Infrastructure.Persistence;

/// <summary>
/// Database settings. The connection string is a secret and comes only from the environment
/// (ConnectionStrings__Amr); nothing in the repository contains one.
/// </summary>
public sealed class DatabaseOptions
{
    public const string SectionName = "Database";
    public const string ConnectionStringName = "Amr";

    [Required(ErrorMessage = "The ConnectionStrings:Amr setting is required. Set the ConnectionStrings__Amr environment variable.")]
    public string? ConnectionString { get; set; }

    [Range(1, 600)]
    public int CommandTimeoutSeconds { get; init; } = 30;

    [Range(1, 60)]
    public int HealthTimeoutSeconds { get; init; } = 3;
}
