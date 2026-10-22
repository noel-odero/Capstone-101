using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Amr.Infrastructure.Persistence.Migrations
{
    /// <inheritdoc />
    public partial class AddUsers : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "users",
                columns: table => new
                {
                    id = table.Column<Guid>(type: "uuid", nullable: false),
                    email = table.Column<string>(type: "character varying(254)", maxLength: 254, nullable: false),
                    normalized_email = table.Column<string>(type: "character varying(254)", maxLength: 254, nullable: false),
                    display_name = table.Column<string>(type: "character varying(80)", maxLength: 80, nullable: false),
                    password_hash = table.Column<string>(type: "character varying(256)", maxLength: 256, nullable: false),
                    failed_sign_in_count = table.Column<int>(type: "integer", nullable: false),
                    locked_until_utc = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: true),
                    created_at_utc = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_users", x => x.id);
                    table.CheckConstraint("ck_users_failed_sign_in_count", "failed_sign_in_count >= 0");
                });

            migrationBuilder.CreateIndex(
                name: "ux_users_normalized_email",
                table: "users",
                column: "normalized_email",
                unique: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "users");
        }
    }
}
