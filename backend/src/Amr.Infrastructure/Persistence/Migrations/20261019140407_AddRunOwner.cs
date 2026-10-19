using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Amr.Infrastructure.Persistence.Migrations
{
    /// <inheritdoc />
    public partial class AddRunOwner : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(
                name: "owner_id",
                table: "experiment_runs",
                type: "character varying(200)",
                maxLength: 200,
                nullable: false,
                defaultValue: "");

            migrationBuilder.CreateIndex(
                name: "ix_experiment_runs_owner_recent",
                table: "experiment_runs",
                columns: new[] { "owner_id", "created_at_utc", "id" },
                descending: new[] { false, true, true });
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropIndex(
                name: "ix_experiment_runs_owner_recent",
                table: "experiment_runs");

            migrationBuilder.DropColumn(
                name: "owner_id",
                table: "experiment_runs");
        }
    }
}
