using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Amr.Infrastructure.Persistence.Migrations
{
    /// <inheritdoc />
    public partial class AddDqnStrategy : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropCheckConstraint(
                name: "ck_strategy_runs_strategy",
                table: "strategy_runs");

            migrationBuilder.AddColumn<string>(
                name: "model",
                table: "strategy_runs",
                type: "jsonb",
                nullable: true);

            migrationBuilder.AddCheckConstraint(
                name: "ck_strategy_runs_strategy",
                table: "strategy_runs",
                sql: "strategy IN ('ppo', 'dqn', 'random_susceptible_baseline')");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropCheckConstraint(
                name: "ck_strategy_runs_strategy",
                table: "strategy_runs");

            migrationBuilder.DropColumn(
                name: "model",
                table: "strategy_runs");

            migrationBuilder.AddCheckConstraint(
                name: "ck_strategy_runs_strategy",
                table: "strategy_runs",
                sql: "strategy IN ('ppo', 'random_susceptible_baseline')");
        }
    }
}
