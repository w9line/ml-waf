#!/usr/bin/env bash
set -euo pipefail
mkdir -p /run/aegis
cd /opt/aegis/app
CONFIG=${AEGIS_CONFIG:-/opt/aegis/lab/config.yaml}
AEGIS_CONFIG="$CONFIG" mitmdump --mode transparent --listen-host 0.0.0.0 --listen-port 18080 -s /opt/aegis/app/aegis/addon.py >/tmp/mitm.log 2>&1 &
proxy=$!
printf "%s\n" "$proxy" > /run/aegis/proxy.pid
AEGIS_CONFIG="$CONFIG" AEGIS_PROXY_PIDFILE=/run/aegis/proxy.pid python -m aegis.controller --config "$CONFIG" >/tmp/discovery.log 2>&1 &
discovery=$!
printf "%s\n" "$discovery" > /run/aegis/discovery.pid
AEGIS_CONFIG="$CONFIG" AEGIS_PROXY_PIDFILE=/run/aegis/proxy.pid AEGIS_WATCHDOG_LOOP=1 AEGIS_WATCHDOG_INTERVAL=0.5 python -m aegis.watchdog >/tmp/watchdog.log 2>&1 &
wait "$proxy" || true
while true; do sleep 60; done
