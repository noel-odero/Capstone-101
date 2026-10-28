#!/usr/bin/env bash
set -euo pipefail
umask 077

[[ "$EUID" -eq 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
[[ $# -eq 0 || ( $# -eq 1 && "$1" == '--check' ) ]] || exit 64

app_directory=/opt/stewardlab
state_directory=/var/lib/stewardlab-deploy
repository=noel-odero/Capstone-101
mkdir -p "$state_directory"
exec 9>"$state_directory/lock"
flock -n 9 || exit 0
cd "$app_directory"
export GIT_TERMINAL_PROMPT=0
git_app() { runuser -u azureuser -- git "$@"; }

[[ "$(git_app remote get-url origin)" == "https://github.com/$repository.git" ]] || {
  echo 'Unexpected origin; refusing deployment.' >&2; exit 1;
}
[[ "$(git_app branch --show-current)" == main ]] || {
  echo 'The deployment checkout must be on main.' >&2; exit 1;
}
if ! git_app diff --quiet || ! git_app diff --cached --quiet; then
  echo 'Tracked server files have local changes; refusing deployment.' >&2
  exit 1
fi
git_app fetch --quiet --no-tags origin main
target="$(git_app rev-parse FETCH_HEAD)"
[[ "$target" =~ ^[0-9a-f]{40}$ ]] || exit 1
deployed="$(cat "$state_directory/deployed" 2>/dev/null || true)"
[[ "$target" != "$deployed" ]] || exit 0

response="$(mktemp)"
trap 'rm -f -- "$response"' EXIT
curl --fail --silent --show-error --connect-timeout 10 --max-time 30 \
  -H 'Accept: application/vnd.github+json' -H 'X-GitHub-Api-Version: 2022-11-28' \
  "https://api.github.com/repos/$repository/actions/workflows/ci.yml/runs?branch=main&event=push&head_sha=$target&per_page=1" \
  > "$response"

if ! python3 - "$response" "$target" "$repository" <<'PY'
import json
import sys

with open(sys.argv[1]) as source:
    runs = json.load(source).get("workflow_runs", [])
run = runs[0] if runs else {}
passed = (
    run.get("head_sha") == sys.argv[2]
    and run.get("head_branch") == "main"
    and run.get("event") == "push"
    and run.get("head_repository", {}).get("full_name") == sys.argv[3]
    and run.get("status") == "completed"
    and run.get("conclusion") == "success"
)
sys.exit(0 if passed else 1)
PY
then
  echo "Waiting for successful main CI at $target. Current deployment unchanged."
  exit 0
fi

git_app merge-base --is-ancestor HEAD "$target" || {
  echo 'Main diverged from the server checkout; resolve it manually.' >&2; exit 1;
}
if [[ "${1:-}" == '--check' ]]; then
  echo "CI passed for $target. Check only; no containers changed."
  exit 0
fi
if [[ "$(cat "$state_directory/failed" 2>/dev/null || true)" == "$target" ]]; then
  echo "Deployment previously failed for $target. Inspect the journal before retrying." >&2
  exit 1
fi

frontend_only=false
if [[ "$deployed" =~ ^[0-9a-f]{40}$ ]] && git_app cat-file -e "$deployed^{commit}"; then
  frontend_only=true
  while IFS= read -r file; do
    case "$file" in
      frontend/*|docs/*|README.md|deploy/web.Dockerfile|deploy/Caddyfile) ;;
      *) frontend_only=false; break ;;
    esac
  done < <(git_app diff --name-only "$deployed" "$target")
fi

trap 'printf "%s\n" "$target" > "$state_directory/failed"; echo "Deployment failed. Inspect journalctl -u stewardlab-autodeploy.service; no automatic rollback was attempted." >&2' ERR
echo "Deploying tested main commit $target."
git_app merge --ff-only "$target"
docker compose config --quiet

if "$frontend_only"; then
  docker compose build web
  docker compose up -d --no-deps --wait --wait-timeout 120 web
else
  # Build before interrupting the API. A failed migration needs manual review.
  docker compose --parallel 1 build
  bash deploy/backup.sh
  docker compose stop api
  docker compose --profile tools run --rm migrate
  docker compose up -d --wait --wait-timeout 240
fi

# Read only the public hostname from .env; do not source a secrets file as shell code.
domain="$(python3 - <<'PY'
from pathlib import Path
import re

values = [line.split("=", 1)[1].strip().strip("\"'")
          for line in Path(".env").read_text().splitlines() if line.startswith("DOMAIN=")]
if len(values) != 1 or not re.fullmatch(r"[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*", values[0]):
    raise SystemExit("Expected one valid DOMAIN setting")
print(values[0])
PY
)"
curl --fail --silent --show-error --retry 4 --retry-delay 3 --max-time 15 \
  "https://$domain/api/v1/health" \
  | python3 -c 'import json,sys; result=json.load(sys.stdin); sys.exit(0 if result.get("status")=="healthy" and result.get("ready") is True else 1)'
printf '%s\n' "$target" > "$state_directory/deployed.tmp"
mv -- "$state_directory/deployed.tmp" "$state_directory/deployed"
rm -f -- "$state_directory/failed"
echo "Deployment healthy: $target."
