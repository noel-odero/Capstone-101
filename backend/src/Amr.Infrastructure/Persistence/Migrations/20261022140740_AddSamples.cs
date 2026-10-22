using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Amr.Infrastructure.Persistence.Migrations
{
    /// <inheritdoc />
    public partial class AddSamples : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<Guid>(
                name: "sample_id",
                table: "experiment_runs",
                type: "uuid",
                nullable: true);

            migrationBuilder.CreateTable(
                name: "samples",
                columns: table => new
                {
                    id = table.Column<Guid>(type: "uuid", nullable: false),
                    owner_id = table.Column<string>(type: "character varying(200)", maxLength: 200, nullable: false),
                    label = table.Column<string>(type: "character varying(80)", maxLength: 80, nullable: false),
                    added_at_utc = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false),
                    initial_profile = table.Column<int[]>(type: "integer[]", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_samples", x => x.id);
                    table.UniqueConstraint("AK_samples_id_owner_id", x => new { x.id, x.owner_id });
                    table.CheckConstraint("ck_samples_label", "length(btrim(label)) > 0");
                    table.CheckConstraint("ck_samples_profile", "cardinality(initial_profile) = 7 AND initial_profile <@ ARRAY[0,1]");
                });

            migrationBuilder.CreateIndex(
                name: "IX_experiment_runs_sample_id_owner_id",
                table: "experiment_runs",
                columns: new[] { "sample_id", "owner_id" });

            migrationBuilder.CreateIndex(
                name: "IX_samples_owner_id_added_at_utc",
                table: "samples",
                columns: new[] { "owner_id", "added_at_utc" });

            migrationBuilder.AddForeignKey(
                name: "FK_experiment_runs_samples_sample_id_owner_id",
                table: "experiment_runs",
                columns: new[] { "sample_id", "owner_id" },
                principalTable: "samples",
                principalColumns: new[] { "id", "owner_id" },
                onDelete: ReferentialAction.Restrict);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_experiment_runs_samples_sample_id_owner_id",
                table: "experiment_runs");

            migrationBuilder.DropTable(
                name: "samples");

            migrationBuilder.DropIndex(
                name: "IX_experiment_runs_sample_id_owner_id",
                table: "experiment_runs");

            migrationBuilder.DropColumn(
                name: "sample_id",
                table: "experiment_runs");
        }
    }
}
