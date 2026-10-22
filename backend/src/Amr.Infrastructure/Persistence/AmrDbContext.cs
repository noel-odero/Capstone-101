using System.Text.Json;
using Amr.Domain.Enums;
using Amr.Infrastructure.Persistence.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.ChangeTracking;
using Microsoft.EntityFrameworkCore.Storage.ValueConversion;

namespace Amr.Infrastructure.Persistence;

/// <summary>
/// Schema for stored runs. Tables and columns are snake_case; integrity (keys, uniqueness, ranges, array lengths and the
/// completed-only status) is enforced by the database, not just by the application.
/// </summary>
public sealed class AmrDbContext(DbContextOptions<AmrDbContext> options) : DbContext(options)
{
    private const int ProfileLength = 7;
    private const string Sha256Pattern = "^[0-9a-f]{64}$";

    public DbSet<ModelVersion> ModelVersions => Set<ModelVersion>();

    public DbSet<ExperimentRun> ExperimentRuns => Set<ExperimentRun>();

    public DbSet<StrategyRun> StrategyRuns => Set<StrategyRun>();

    public DbSet<StepTrace> StepTraces => Set<StepTrace>();

    public DbSet<AppUser> Users => Set<AppUser>();
    public DbSet<Sample> Samples => Set<Sample>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        ConfigureModelVersion(modelBuilder);
        ConfigureExperimentRun(modelBuilder);
        ConfigureStrategyRun(modelBuilder);
        ConfigureStepTrace(modelBuilder);
        ConfigureUser(modelBuilder);
        modelBuilder.Entity<Sample>(entity =>
        {
            entity.ToTable("samples", table =>
            {
                table.HasCheckConstraint("ck_samples_profile", "cardinality(initial_profile) = 7 AND initial_profile <@ ARRAY[0,1]");
                table.HasCheckConstraint("ck_samples_label", "length(btrim(label)) > 0");
            });
            entity.HasKey(sample => sample.Id);
            entity.Property(sample => sample.Id).ValueGeneratedNever();
            entity.Property(sample => sample.OwnerId).HasMaxLength(200).IsRequired();
            entity.Property(sample => sample.Label).HasMaxLength(80).IsRequired();
            entity.HasAlternateKey(sample => new { sample.Id, sample.OwnerId });
            entity.HasIndex(sample => new { sample.OwnerId, sample.AddedAtUtc });
        });
        modelBuilder.Entity<ExperimentRun>().HasOne<Sample>().WithMany()
            .HasForeignKey(run => new { run.SampleId, run.OwnerId })
            .HasPrincipalKey(sample => new { sample.Id, sample.OwnerId })
            .OnDelete(DeleteBehavior.Restrict);
        ApplySnakeCaseNames(modelBuilder);
    }

    private static void ConfigureModelVersion(ModelBuilder modelBuilder) =>
        modelBuilder.Entity<ModelVersion>(entity =>
        {
            entity.ToTable("model_versions", table =>
            {
                table.HasCheckConstraint("ck_model_versions_checkpoint_sha256", $"checkpoint_sha256 ~ '{Sha256Pattern}'");
                table.HasCheckConstraint("ck_model_versions_interaction_data_sha256", $"interaction_data_sha256 ~ '{Sha256Pattern}'");
                table.HasCheckConstraint("ck_model_versions_fingerprint", $"fingerprint ~ '{Sha256Pattern}'");
                table.HasCheckConstraint("ck_model_versions_horizon", "horizon > 0");
                table.HasCheckConstraint("ck_model_versions_antibiotic_order", $"cardinality(antibiotic_order) = {ProfileLength}");
            });
            entity.HasKey(model => model.Id);
            entity.Property(model => model.Id).ValueGeneratedNever();
            entity.Property(model => model.Fingerprint).HasMaxLength(64).IsFixedLength();
            entity.Property(model => model.CheckpointSha256).HasMaxLength(64).IsFixedLength();
            entity.Property(model => model.InteractionDataSha256).HasMaxLength(64).IsFixedLength();
            entity.Property(model => model.RewardSpecificationJson).HasColumnType("jsonb");
            entity.HasIndex(model => model.Fingerprint).IsUnique().HasDatabaseName("ux_model_versions_fingerprint");
            entity.HasIndex(model => model.CheckpointSha256).HasDatabaseName("ix_model_versions_checkpoint_sha256");
        });

    private static void ConfigureExperimentRun(ModelBuilder modelBuilder) =>
        modelBuilder.Entity<ExperimentRun>(entity =>
        {
            entity.ToTable("experiment_runs", table =>
            {
                table.HasCheckConstraint("ck_experiment_runs_status", "status = 'completed'");
                table.HasCheckConstraint("ck_experiment_runs_kind", "kind IN ('simulation', 'comparison')");
                table.HasCheckConstraint("ck_experiment_runs_initial_profile", $"cardinality(initial_profile) = {ProfileLength}");
                table.HasCheckConstraint("ck_experiment_runs_environment_seed", "environment_seed BETWEEN 0 AND 4294967295");
                table.HasCheckConstraint("ck_experiment_runs_policy_seed", "policy_seed IS NULL OR policy_seed BETWEEN 0 AND 4294967295");
                table.HasCheckConstraint(
                    "ck_experiment_runs_comparison_columns",
                    "(kind = 'comparison' AND pairing_semantics IS NOT NULL AND single_run_caveat IS NOT NULL AND comparison_contract IS NOT NULL) " +
                    "OR (kind = 'simulation' AND pairing_semantics IS NULL AND single_run_caveat IS NULL AND comparison_contract IS NULL)");
            });
            entity.HasKey(run => run.Id);
            entity.Property(run => run.Id).ValueGeneratedNever();
            entity.Property(run => run.OwnerId).HasMaxLength(200).IsRequired();
            entity.Property(run => run.Kind).HasConversion(SnakeCaseEnum<ExperimentKind>()).HasMaxLength(16);
            entity.Property(run => run.Status).HasConversion(SnakeCaseEnum<RunStatus>()).HasMaxLength(16);
            entity.Property(run => run.MetricDefinitionsJson).HasColumnType("jsonb");
            entity.Property(run => run.ComparisonContractJson).HasColumnType("jsonb");
            entity.HasOne(run => run.ModelVersion)
                .WithMany(model => model.ExperimentRuns)
                .HasForeignKey(run => run.ModelVersionId)
                .OnDelete(DeleteBehavior.Restrict);
            entity.HasIndex(run => new { run.CreatedAtUtc, run.Id })
                .IsDescending(true, true)
                .HasDatabaseName("ix_experiment_runs_recent");
            entity.HasIndex(run => new { run.OwnerId, run.CreatedAtUtc, run.Id })
                .IsDescending(false, true, true)
                .HasDatabaseName("ix_experiment_runs_owner_recent");
        });

    private static void ConfigureStrategyRun(ModelBuilder modelBuilder) =>
        modelBuilder.Entity<StrategyRun>(entity =>
        {
            entity.ToTable("strategy_runs", table =>
            {
                table.HasCheckConstraint("ck_strategy_runs_strategy", "strategy IN ('ppo', 'random_susceptible_baseline')");
                table.HasCheckConstraint("ck_strategy_runs_profiles", $"cardinality(initial_profile) = {ProfileLength} AND cardinality(final_profile) = {ProfileLength}");
                table.HasCheckConstraint("ck_strategy_runs_environment_seed", "environment_seed BETWEEN 0 AND 4294967295");
                table.HasCheckConstraint("ck_strategy_runs_policy_seed", "policy_seed IS NULL OR policy_seed BETWEEN 0 AND 4294967295");
                table.HasCheckConstraint("ck_strategy_runs_counts", $"initial_resistant_count BETWEEN 0 AND {ProfileLength} AND final_resistant_count BETWEEN 0 AND {ProfileLength} AND final_susceptible_count BETWEEN 0 AND {ProfileLength} AND treatment_steps >= 0 AND unsupported_step_count BETWEEN 0 AND treatment_steps");
            });
            entity.HasKey(strategy => strategy.Id);
            entity.Property(strategy => strategy.Id).ValueGeneratedNever();
            entity.Property(strategy => strategy.Strategy).HasConversion(SnakeCaseEnum<StrategyKind>()).HasMaxLength(32);
            entity.Property(strategy => strategy.StatesJson).HasColumnType("jsonb");
            entity.HasOne(strategy => strategy.ExperimentRun)
                .WithMany(run => run.StrategyRuns)
                .HasForeignKey(strategy => strategy.ExperimentRunId)
                .OnDelete(DeleteBehavior.Cascade);
            entity.HasIndex(strategy => new { strategy.ExperimentRunId, strategy.Strategy })
                .IsUnique()
                .HasDatabaseName("ux_strategy_runs_run_strategy");
        });

    private static void ConfigureStepTrace(ModelBuilder modelBuilder) =>
        modelBuilder.Entity<StepTrace>(entity =>
        {
            entity.ToTable("step_traces", table =>
            {
                table.HasCheckConstraint("ck_step_traces_step_index", "step_index >= 0");
                table.HasCheckConstraint("ck_step_traces_action_id", $"action_id BETWEEN 0 AND {ProfileLength - 1}");
                table.HasCheckConstraint("ck_step_traces_profiles", $"cardinality(resistance_profile_before) = {ProfileLength} AND cardinality(resistance_profile_after) = {ProfileLength}");
                table.HasCheckConstraint("ck_step_traces_transition_seed", "transition_seed IS NULL OR transition_seed >= 0");
            });
            entity.HasKey(step => new { step.StrategyRunId, step.StepIndex });
            entity.Property(step => step.FeasibleActionsJson).HasColumnType("jsonb");
            entity.Property(step => step.CandidateTransitionsJson).HasColumnType("jsonb");
            entity.HasOne(step => step.StrategyRun)
                .WithMany(strategy => strategy.StepTraces)
                .HasForeignKey(step => step.StrategyRunId)
                .OnDelete(DeleteBehavior.Cascade);
        });

    private static void ConfigureUser(ModelBuilder modelBuilder) =>
        modelBuilder.Entity<AppUser>(entity =>
        {
            entity.ToTable("users", table => table.HasCheckConstraint("ck_users_failed_sign_in_count", "failed_sign_in_count >= 0"));
            entity.HasKey(user => user.Id);
            entity.Property(user => user.Id).ValueGeneratedNever();
            entity.Property(user => user.Email).HasMaxLength(254);
            entity.Property(user => user.NormalizedEmail).HasMaxLength(254);
            entity.Property(user => user.DisplayName).HasMaxLength(80);
            entity.Property(user => user.PasswordHash).HasMaxLength(256);
            entity.HasIndex(user => user.NormalizedEmail).IsUnique().HasDatabaseName("ux_users_normalized_email");
        });

    private static ValueConverter<TEnum, string> SnakeCaseEnum<TEnum>()
        where TEnum : struct, Enum
    {
        var names = Enum.GetValues<TEnum>().ToDictionary(value => value, value => JsonNamingPolicy.SnakeCaseLower.ConvertName(value.ToString()));
        var values = names.ToDictionary(pair => pair.Value, pair => pair.Key, StringComparer.Ordinal);
        return new ValueConverter<TEnum, string>(value => names[value], text => values[text]);
    }

    private static void ApplySnakeCaseNames(ModelBuilder modelBuilder)
    {
        foreach (var entity in modelBuilder.Model.GetEntityTypes())
        {
            foreach (var property in entity.GetProperties())
            {
                property.SetColumnName(JsonNamingPolicy.SnakeCaseLower.ConvertName(RemoveJsonSuffix(property.Name)));
            }
        }
    }

    private static string RemoveJsonSuffix(string name) => name.EndsWith("Json", StringComparison.Ordinal) ? name[..^4] : name;
}
