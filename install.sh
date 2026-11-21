#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ $(id -u) -ne 0 ]]; then echo "Run as root" >&2; exit 1; fi
command -v apt-get >/dev/null || { echo "Ubuntu apt-get is required" >&2; exit 1; }
apt-get update
apt-get install -y nftables iproute2 python3-venv curl
for tool in nft ss systemctl python3; do command -v "$tool" >/dev/null || { echo "Missing prerequisite: $tool" >&2; exit 1; }; done
PYTHON=python3
if ! python3 -c "import sys; raise SystemExit(sys.version_info < (3,11))"; then
  apt-get install -y python3.11 python3.11-venv
  PYTHON=python3.11
fi
"$PYTHON" -c "import sys; assert sys.version_info >= (3,11)"
"$PYTHON" -m venv /opt/aegis/venv
install -d -m 0755 /opt/aegis/app/aegis /opt/aegis/models /etc/aegis /var/lib/aegis
cp -a "$ROOT/aegis/." /opt/aegis/app/aegis/
install -m 0644 "$ROOT/pyproject.toml" /opt/aegis/app/pyproject.toml
install -m 0644 "$ROOT/models/README.md" "$ROOT/models/ATTRIBUTION.md" /opt/aegis/models/
install -m 0755 "$ROOT/models/get_weights.sh" /opt/aegis/models/get_weights.sh
/opt/aegis/venv/bin/python -m pip install --upgrade pip
/opt/aegis/venv/bin/pip install "/opt/aegis/app[ml]"
if [[ ! -e /etc/aegis/config.yaml ]]; then
  install -m 0640 "$ROOT/config.yaml" /etc/aegis/config.yaml
else
  echo "Preserving existing /etc/aegis/config.yaml"
fi
for unit in aegis-proxy.service aegis-discovery.service aegis-watchdog.service aegis-watchdog.timer; do install -m 0644 "$ROOT/systemd/$unit" /etc/systemd/system/; done
systemctl daemon-reload
echo "Installed Aegis dependencies and systemd units. Review /etc/aegis/config.yaml, then run ./start.sh."
