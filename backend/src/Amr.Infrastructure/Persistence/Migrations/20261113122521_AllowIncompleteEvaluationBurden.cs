using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Amr.Infrastructure.Persistence.Migrations
{
    /// <inheritdoc />
    public partial class AllowIncompleteEvaluationBurden : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AlterColumn<double>(
                name: "cumulative_resistance_burden",
                table: "strategy_runs",
                type: "double precision",
                nullable: true,
                oldClrType: typeof(double),
                oldType: "double precision");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.Sql("""
                DO $$ BEGIN
                  IF EXISTS (SELECT 1 FROM strategy_runs WHERE cumulative_resistance_burden IS NULL) THEN
                    RAISE EXCEPTION 'Cannot downgrade: incomplete evaluations have unknown full-horizon burden.';
                  END IF;
                END $$;
                """);
            migrationBuilder.AlterColumn<double>(
                name: "cumulative_resistance_burden",
                table: "strategy_runs",
                type: "double precision",
                nullable: false,
                oldClrType: typeof(double),
                oldType: "double precision",
                oldNullable: true);
        }
    }
}
