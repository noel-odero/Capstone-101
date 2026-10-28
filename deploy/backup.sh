#!/usr/bin/env bash
set -euo pipefail
umask 077

app_directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$app_directory"
mkdir -p backups
destination="backups/amr-$(date -u +%Y%m%dT%H%M%SZ).dump"

docker compose exec -T postgres pg_dump -U amr -d amr --format=custom > "${destination}.tmp"
test -s "${destination}.tmp"
mv -- "${destination}.tmp" "$destination"
printf 'Database backup written to %s\n' "$destination"
