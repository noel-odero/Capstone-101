using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Amr.Infrastructure.Persistence.Migrations
{
    /// <inheritdoc />
    public partial class RequireEmailVerification : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<DateTimeOffset>(
                name: "email_verified_at_utc",
                table: "users",
                type: "timestamp with time zone",
                nullable: true);

            migrationBuilder.CreateTable(
                name: "email_verifications",
                columns: table => new
                {
                    normalized_email = table.Column<string>(type: "character varying(254)", maxLength: 254, nullable: false),
                    email = table.Column<string>(type: "character varying(254)", maxLength: 254, nullable: false),
                    display_name = table.Column<string>(type: "character varying(80)", maxLength: 80, nullable: false),
                    password_hash = table.Column<string>(type: "character varying(256)", maxLength: 256, nullable: true),
                    user_id = table.Column<Guid>(type: "uuid", nullable: true),
                    ticket_hash = table.Column<string>(type: "character varying(64)", maxLength: 64, nullable: true),
                    code_hash = table.Column<string>(type: "character varying(64)", maxLength: 64, nullable: true),
                    sent_at_utc = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false),
                    expires_at_utc = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false),
                    send_window_started_at_utc = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false),
                    send_count = table.Column<int>(type: "integer", nullable: false),
                    failed_attempts = table.Column<int>(type: "integer", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_email_verifications", x => x.normalized_email);
                    table.CheckConstraint("ck_email_verifications_attempts", "failed_attempts BETWEEN 0 AND 5");
                    table.CheckConstraint("ck_email_verifications_sends", "send_count BETWEEN 1 AND 5");
                });

            migrationBuilder.CreateIndex(
                name: "IX_email_verifications_ticket_hash",
                table: "email_verifications",
                column: "ticket_hash",
                unique: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "email_verifications");

            migrationBuilder.DropColumn(
                name: "email_verified_at_utc",
                table: "users");
        }
    }
}
