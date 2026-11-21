#!/usr/bin/env bash
set -euo pipefail
systemctl stop aegis-watchdog.timer aegis-discovery.service aegis-proxy.service 2>/dev/null || true
nft delete table inet aegis 2>/dev/null || true
