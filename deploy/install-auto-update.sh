#!/usr/bin/env bash
set -euo pipefail

[[ "$EUID" -eq 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
script_directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd /opt/stewardlab
[[ -f "$script_directory/auto-update.sh" && -f .env ]] || exit 1
install -o root -g root -m 0755 "$script_directory/auto-update.sh" /usr/local/sbin/stewardlab-autodeploy

cat > /etc/systemd/system/stewardlab-autodeploy.service <<'UNIT'
[Unit]
Description=Deploy StewardLab main after successful GitHub CI
Wants=network-online.target
After=network-online.target docker.service
Requires=docker.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/stewardlab-autodeploy
TimeoutStartSec=30min
UMask=0077
Nice=10
UNIT

cat > /etc/systemd/system/stewardlab-autodeploy.timer <<'UNIT'
[Unit]
Description=Check StewardLab for tested updates every two minutes

[Timer]
OnBootSec=2min
OnUnitInactiveSec=2min
AccuracySec=10s
Unit=stewardlab-autodeploy.service

[Install]
WantedBy=timers.target
UNIT

systemctl daemon-reload
systemctl enable --now stewardlab-autodeploy.timer
echo 'Automatic deployment enabled. Logs: journalctl -u stewardlab-autodeploy.service'
