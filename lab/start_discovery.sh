#!/usr/bin/env bash
set -euo pipefail
AEGIS_CONFIG=/opt/aegis/lab/config.yaml AEGIS_PROXY_PIDFILE=/run/aegis/proxy.pid python -m aegis.controller --config /opt/aegis/lab/config.yaml >/tmp/restart-discovery.log 2>&1 &
echo $! > /run/aegis/discovery.pid
