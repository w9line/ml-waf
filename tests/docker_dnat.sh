#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
DC=(docker compose -p aegis-dnat -f lab/compose.yaml -f lab/compose.docker-dnat.yaml)
cleanup() { "${DC[@]}" exec -T aegis nft delete table ip lab_docker_nat >/dev/null 2>&1 || true; "${DC[@]}" down --remove-orphans >/dev/null 2>&1 || true; }
trap cleanup EXIT
"${DC[@]}" up -d --build
for i in $(seq 1 60); do status=$(docker inspect aegis-dnat-aegis-1 --format "{{.State.Health.Status}}" 2>/dev/null || true); [[ "$status" == healthy ]] && break; sleep 1; done
[[ "$(docker inspect aegis-dnat-aegis-1 --format "{{.State.Health.Status}}")" == healthy ]]
"${DC[@]}" exec -T aegis bash /opt/aegis/lab/setup_docker_dnat.sh
for i in $(seq 1 20); do ports=$("${DC[@]}" exec -T aegis nft list set inet aegis http_ports 2>/dev/null || true); [[ "$ports" == *15000* ]] && break; sleep 1; done
[[ "$ports" == *15000* ]]
response=$("${DC[@]}" exec -T client curl -fsS --max-time 5 -H "Host: proof.internal" "http://172.29.0.2:15000/path?a=1&b=two")
python3 lab/verify.py get "$response"
"${DC[@]}" exec -T aegis python /opt/aegis/lab/verify_docker_dnat.py
"${DC[@]}" exec -T aegis nft list chain inet aegis prerouting
echo docker-dnat-equivalent-integration-PASS
