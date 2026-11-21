#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
DC=(docker compose -p aegis-observe -f lab/compose.yaml -f lab/compose.observe.yaml)
cleanup() { "${DC[@]}" down --remove-orphans >/dev/null 2>&1 || true; }
trap cleanup EXIT
"${DC[@]}" up -d --build
for i in $(seq 1 120); do
  status=$(docker inspect aegis-observe-aegis-1 --format "{{.State.Health.Status}}" 2>/dev/null || true)
  [[ "$status" == healthy ]] && break
  sleep 1
done
[[ "$(docker inspect aegis-observe-aegis-1 --format "{{.State.Health.Status}}")" == healthy ]]
"${DC[@]}" exec -T client python /opt/aegis/lab/observe_client.py
"${DC[@]}" exec -T aegis python /opt/aegis/lab/verify_observer.py
"${DC[@]}" exec -T aegis nft list chain inet aegis prerouting
 echo observe-only-integration-PASS
