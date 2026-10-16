using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Amr.Infrastructure.Persistence.Migrations
{
    /// <inheritdoc />
    public partial class InitialCreate : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "model_versions",
                columns: table => new
                {
                    id = table.Column<Guid>(type: "uuid", nullable: false),
                    fingerprint = table.Column<string>(type: "character(64)", fixedLength: true, maxLength: 64, nullable: false),
                    model_id = table.Column<string>(type: "text", nullable: false),
                    algorithm = table.Column<string>(type: "text", nullable: false),
                    checkpoint_sha256 = table.Column<string>(type: "character(64)", fixedLength: true, maxLength: 64, nullable: false),
                    interaction_data_sha256 = table.Column<string>(type: "character(64)", fixedLength: true, maxLength: 64, nullable: false),
                    scenario_id = table.Column<string>(type: "text", nullable: false),
                    horizon = table.Column<int>(type: "integer", nullable: false),
                    action_mask_rule = table.Column<string>(type: "text", nullable: false),
                    reward_specification = table.Column<string>(type: "jsonb", nullable: false),
                    antibiotic_order = table.Column<string[]>(type: "text[]", nullable: false),
                    first_recorded_at_utc = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_model_versions", x => x.id);
                    table.CheckConstraint("ck_model_versions_antibiotic_order", "cardinality(antibiotic_order) = 7");
                    table.CheckConstraint("ck_model_versions_checkpoint_sha256", "checkpoint_sha256 ~ '^[0-9a-f]{64}$'");
                    table.CheckConstraint("ck_model_versions_fingerprint", "fingerprint ~ '^[0-9a-f]{64}$'");
                    table.CheckConstraint("ck_model_versions_horizon", "horizon > 0");
                    table.CheckConstraint("ck_model_versions_interaction_data_sha256", "interaction_data_sha256 ~ '^[0-9a-f]{64}$'");
                });

            migrationBuilder.CreateTable(
                name: "experiment_runs",
                columns: table => new
                {
                    id = table.Column<Guid>(type: "uuid", nullable: false),
                    kind = table.Column<string>(type: "character varying(16)", maxLength: 16, nullable: false),
                    status = table.Column<string>(type: "character varying(16)", maxLength: 16, nullable: false),
                    model_version_id = table.Column<Guid>(type: "uuid", nullable: false),
                    service_version = table.Column<string>(type: "text", nullable: false),
                    created_at_utc = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false),
                    recorded_at_utc = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false),
                    initial_profile = table.Column<int[]>(type: "integer[]", nullable: false),
                    environment_seed = table.Column<long>(type: "bigint", nullable: false),
                    environment_seed_source = table.Column<string>(type: "text", nullable: false),
                    policy_seed = table.Column<long>(type: "bigint", nullable: true),
                    policy_seed_source = table.Column<string>(type: "text", nullable: false),
                    seed_notes = table.Column<string[]>(type: "text[]", nullable: false),
                    disclaimer = table.Column<string>(type: "text", nullable: false),
                    metric_definitions = table.Column<string>(type: "jsonb", nullable: false),
                    pairing_semantics = table.Column<string>(type: "text", nullable: true),
                    single_run_caveat = table.Column<string>(type: "text", nullable: true),
                    comparison_contract = table.Column<string>(type: "jsonb", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_experiment_runs", x => x.id);
                    table.CheckConstraint("ck_experiment_runs_comparison_columns", "(kind = 'comparison' AND pairing_semantics IS NOT NULL AND single_run_caveat IS NOT NULL AND comparison_contract IS NOT NULL) OR (kind = 'simulation' AND pairing_semantics IS NULL AND single_run_caveat IS NULL AND comparison_contract IS NULL)");
                    table.CheckConstraint("ck_experiment_runs_environment_seed", "environment_seed BETWEEN 0 AND 4294967295");
                    table.CheckConstraint("ck_experiment_runs_initial_profile", "cardinality(initial_profile) = 7");
                    table.CheckConstraint("ck_experiment_runs_kind", "kind IN ('simulation', 'comparison')");
                    table.CheckConstraint("ck_experiment_runs_policy_seed", "policy_seed IS NULL OR policy_seed BETWEEN 0 AND 4294967295");
                    table.CheckConstraint("ck_experiment_runs_status", "status = 'completed'");
                    table.ForeignKey(
                        name: "FK_experiment_runs_model_versions_model_version_id",
                        column: x => x.model_version_id,
                        principalTable: "model_versions",
                        principalColumn: "id",
                        onDelete: ReferentialAction.Restrict);
                });

            migrationBuilder.CreateTable(
                name: "strategy_runs",
                columns: table => new
                {
                    id = table.Column<Guid>(type: "uuid", nullable: false),
                    experiment_run_id = table.Column<Guid>(type: "uuid", nullable: false),
                    strategy = table.Column<string>(type: "character varying(32)", maxLength: 32, nullable: false),
                    display_label = table.Column<string>(type: "text", nullable: false),
                    initial_profile = table.Column<int[]>(type: "integer[]", nullable: false),
                    final_profile = table.Column<int[]>(type: "integer[]", nullable: false),
                    environment_seed = table.Column<long>(type: "bigint", nullable: false),
                    policy_seed = table.Column<long>(type: "bigint", nullable: true),
                    termination_reason = table.Column<string>(type: "text", nullable: false),
                    states = table.Column<string>(type: "jsonb", nullable: false),
                    cumulative_resistance_burden = table.Column<double>(type: "double precision", nullable: false),
                    cumulative_reward = table.Column<double>(type: "double precision", nullable: false),
                    treatment_steps = table.Column<int>(type: "integer", nullable: false),
                    initial_resistant_count = table.Column<int>(type: "integer", nullable: false),
                    final_resistant_count = table.Column<int>(type: "integer", nullable: false),
                    final_susceptible_count = table.Column<int>(type: "integer", nullable: false),
                    change_in_susceptible_count = table.Column<int>(type: "integer", nullable: false),
                    resistance_emergence_events = table.Column<int>(type: "integer", nullable: false),
                    resistance_emergence_rate = table.Column<double>(type: "double precision", nullable: true),
                    susceptible_action_rate = table.Column<double>(type: "double precision", nullable: true),
                    unsupported_step_count = table.Column<int>(type: "integer", nullable: false),
                    cumulative_antibiotic_exposure = table.Column<int>(type: "integer", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_strategy_runs", x => x.id);
                    table.CheckConstraint("ck_strategy_runs_counts", "initial_resistant_count BETWEEN 0 AND 7 AND final_resistant_count BETWEEN 0 AND 7 AND final_susceptible_count BETWEEN 0 AND 7 AND treatment_steps >= 0 AND unsupported_step_count BETWEEN 0 AND treatment_steps");
                    table.CheckConstraint("ck_strategy_runs_environment_seed", "environment_seed BETWEEN 0 AND 4294967295");
                    table.CheckConstraint("ck_strategy_runs_policy_seed", "policy_seed IS NULL OR policy_seed BETWEEN 0 AND 4294967295");
                    table.CheckConstraint("ck_strategy_runs_profiles", "cardinality(initial_profile) = 7 AND cardinality(final_profile) = 7");
                    table.CheckConstraint("ck_strategy_runs_strategy", "strategy IN ('ppo', 'random_susceptible_baseline')");
                    table.ForeignKey(
                        name: "FK_strategy_runs_experiment_runs_experiment_run_id",
                        column: x => x.experiment_run_id,
                        principalTable: "experiment_runs",
                        principalColumn: "id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "step_traces",
                columns: table => new
                {
                    strategy_run_id = table.Column<Guid>(type: "uuid", nullable: false),
                    step_index = table.Column<int>(type: "integer", nullable: false),
                    treatment_step_before = table.Column<int>(type: "integer", nullable: false),
                    treatment_step_after = table.Column<int>(type: "integer", nullable: false),
                    resistance_profile_before = table.Column<int[]>(type: "integer[]", nullable: false),
                    action_id = table.Column<int>(type: "integer", nullable: false),
                    antibiotic = table.Column<string>(type: "text", nullable: false),
                    feasible_actions = table.Column<string>(type: "jsonb", nullable: false),
                    selected_drug_susceptible = table.Column<bool>(type: "boolean", nullable: false),
                    transition_status = table.Column<string>(type: "text", nullable: false),
                    has_candidate_transition = table.Column<bool>(type: "boolean", nullable: false),
                    candidate_transitions = table.Column<string>(type: "jsonb", nullable: false),
                    selected_outcome = table.Column<string>(type: "text", nullable: true),
                    selected_target_drug = table.Column<string>(type: "text", nullable: true),
                    source_ids = table.Column<string[]>(type: "text[]", nullable: false),
                    selected_candidate_probability = table.Column<double>(type: "double precision", nullable: true),
                    no_transition_probability = table.Column<double>(type: "double precision", nullable: true),
                    transition_seed = table.Column<long>(type: "bigint", nullable: true),
                    reward = table.Column<double>(type: "double precision", nullable: false),
                    resistance_profile_after = table.Column<int[]>(type: "integer[]", nullable: false),
                    newly_resistant_antibiotics = table.Column<string[]>(type: "text[]", nullable: false),
                    newly_susceptible_antibiotics = table.Column<string[]>(type: "text[]", nullable: false),
                    resistant_count_after = table.Column<int>(type: "integer", nullable: false),
                    susceptible_count_after = table.Column<int>(type: "integer", nullable: false),
                    is_terminal_after = table.Column<bool>(type: "boolean", nullable: false),
                    termination_reason = table.Column<string>(type: "text", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_step_traces", x => new { x.strategy_run_id, x.step_index });
                    table.CheckConstraint("ck_step_traces_action_id", "action_id BETWEEN 0 AND 6");
                    table.CheckConstraint("ck_step_traces_profiles", "cardinality(resistance_profile_before) = 7 AND cardinality(resistance_profile_after) = 7");
                    table.CheckConstraint("ck_step_traces_step_index", "step_index >= 0");
                    table.CheckConstraint("ck_step_traces_transition_seed", "transition_seed IS NULL OR transition_seed >= 0");
                    table.ForeignKey(
                        name: "FK_step_traces_strategy_runs_strategy_run_id",
                        column: x => x.strategy_run_id,
                        principalTable: "strategy_runs",
                        principalColumn: "id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateIndex(
                name: "IX_experiment_runs_model_version_id",
                table: "experiment_runs",
                column: "model_version_id");

            migrationBuilder.CreateIndex(
                name: "ix_experiment_runs_recent",
                table: "experiment_runs",
                columns: new[] { "created_at_utc", "id" },
                descending: new bool[0]);

            migrationBuilder.CreateIndex(
                name: "ix_model_versions_checkpoint_sha256",
                table: "model_versions",
                column: "checkpoint_sha256");

            migrationBuilder.CreateIndex(
                name: "ux_model_versions_fingerprint",
                table: "model_versions",
                column: "fingerprint",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "ux_strategy_runs_run_strategy",
                table: "strategy_runs",
                columns: new[] { "experiment_run_id", "strategy" },
                unique: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "step_traces");

            migrationBuilder.DropTable(
                name: "strategy_runs");

            migrationBuilder.DropTable(
                name: "experiment_runs");

            migrationBuilder.DropTable(
                name: "model_versions");
        }
    }
}
