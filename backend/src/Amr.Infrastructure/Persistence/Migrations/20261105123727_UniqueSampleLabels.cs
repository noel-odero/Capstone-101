using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Amr.Infrastructure.Persistence.Migrations
{
    /// <inheritdoc />
    public partial class UniqueSampleLabels : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(
                name: "normalized_label",
                table: "samples",
                type: "character varying(80)",
                maxLength: 80,
                nullable: false,
                computedColumnSql: "lower(btrim(label))",
                stored: true);

            // Preserve existing samples and links; keep the oldest label and number later duplicates.
            migrationBuilder.Sql("""
                DO $migration$
                DECLARE
                    duplicate record;
                    candidate text;
                    suffix text;
                    number integer;
                BEGIN
                    FOR duplicate IN
                        SELECT id, owner_id, label FROM (
                            SELECT id, owner_id, label,
                                row_number() OVER (PARTITION BY owner_id, normalized_label ORDER BY added_at_utc, id) AS position
                            FROM samples
                        ) ranked WHERE position > 1 ORDER BY owner_id, id
                    LOOP
                        number := 2;
                        LOOP
                            suffix := ' (' || number || ')';
                            candidate := left(btrim(duplicate.label), 80 - length(suffix)) || suffix;
                            EXIT WHEN NOT EXISTS (
                                SELECT 1 FROM samples
                                WHERE owner_id = duplicate.owner_id AND normalized_label = lower(candidate)
                            );
                            number := number + 1;
                        END LOOP;
                        UPDATE samples SET label = candidate WHERE id = duplicate.id;
                    END LOOP;
                END $migration$;
                """);

            migrationBuilder.CreateIndex(
                name: "ux_samples_owner_normalized_label",
                table: "samples",
                columns: new[] { "owner_id", "normalized_label" },
                unique: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropIndex(
                name: "ux_samples_owner_normalized_label",
                table: "samples");

            migrationBuilder.DropColumn(
                name: "normalized_label",
                table: "samples");
        }
    }
}
