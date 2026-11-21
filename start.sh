#!/usr/bin/env bash
set -euo pipefail
systemctl start aegis-proxy.service aegis-discovery.service aegis-watchdog.timer
