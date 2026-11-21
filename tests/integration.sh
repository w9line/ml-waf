#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
DC=(docker compose -f lab/compose.yaml)
cleanup() { "${DC[@]}" down --remove-orphans >/dev/null 2>&1 || true; }
trap cleanup EXIT
"${DC[@]}" up -d --build
for i in $(seq 1 40); do status=$(docker inspect lab-aegis-1 --format "{{.State.Health.Status}}" 2>/dev/null || true); [[ "$status" == healthy ]] && break; sleep 1; done
[[ $(docker inspect lab-aegis-1 --format "{{.State.Health.Status}}") == healthy ]]
for i in $(seq 1 30); do ports=$("${DC[@]}" exec -T aegis nft list set inet aegis http_ports 2>/dev/null || true); [[ "$ports" == *5000* && "$ports" == *8000* && "$ports" == *8080* ]] && break; sleep 1; done
[[ "$ports" == *5000* && "$ports" == *8000* && "$ports" == *8080* ]]
get=$("${DC[@]}" exec -T client curl -fsS -H "Host: proof.internal" "http://172.29.0.2:5000/path?a=1&b=two")
python3 lab/verify.py get "$get"
post=$("${DC[@]}" exec -T client curl -fsS -H "Host: json.internal" -H "Content-Type: application/json" -d '{"v":42}' "http://172.29.0.2:5000/submit?q=post")
python3 lab/verify.py post "$post"
fast=$("${DC[@]}" exec -T client curl -fsS -H "Host: api.internal" "http://172.29.0.2:8000/x?y=1")
python3 lab/verify.py fastapi "$fast"
nginx=$("${DC[@]}" exec -T client curl -fsS -H "Host: nginx.internal" "http://172.29.0.2:8080/nginx")
python3 lab/verify.py nginx "$nginx"
"${DC[@]}" exec -T client python /opt/aegis/lab/keepalive.py
for i in $(seq 1 30); do ports=$("${DC[@]}" exec -T aegis nft list set inet aegis http_ports 2>/dev/null || true); [[ "$ports" == *31337* ]] && break; sleep 1; done
[[ "$ports" == *31337* ]]
"${DC[@]}" exec -T client curl -fsS --max-time 5 "http://172.29.0.2:31337/" >/dev/null
echo DYNAMIC-31337-discovered
before=$("${DC[@]}" exec -T aegis nft list chain inet aegis prerouting | python3 lab/packet_count.py)
"${DC[@]}" exec -T client ssh-keyscan -T 2 -p 2222 172.29.0.2 >/dev/null 2>&1
"${DC[@]}" exec -T client curl -fsSk --max-time 5 https://172.29.0.2:8443/ >/dev/null
after=$("${DC[@]}" exec -T aegis nft list chain inet aegis prerouting | python3 lab/packet_count.py)
[[ "$before" == "$after" ]]
echo SSH-HTTPS-bypass-verified
"${DC[@]}" exec -T aegis python /opt/aegis/lab/telemetry_verify.py
"${DC[@]}" exec -T aegis nft list chain inet aegis prerouting
echo DIRECT-baseline
"${DC[@]}" exec -T aegis python /opt/aegis/lab/loadtest.py --url http://127.0.0.1:5000 --requests 1000 --concurrency 50
echo AEGIS-transparent
"${DC[@]}" exec -T client python /opt/aegis/lab/loadtest.py --url http://172.29.0.2:5000 --requests 1000 --concurrency 50
docker stats --no-stream --format "container={{.Name}} cpu={{.CPUPerc}} memory={{.MemUsage}}" lab-aegis-1 lab-app-1
"${DC[@]}" exec -T aegis python /opt/aegis/lab/kill_process.py --file /run/aegis/discovery.pid --signal TERM
"${DC[@]}" exec -T aegis /opt/aegis/app/emergency-stop.sh
"${DC[@]}" exec -T client curl -fsS --max-time 5 "http://172.29.0.2:5000/fail-open" >/dev/null
echo emergency-stop-direct-backend-OK
"${DC[@]}" exec -T aegis /opt/aegis/lab/start_discovery.sh
sleep 3
"${DC[@]}" exec -T aegis python /opt/aegis/lab/kill_process.py --file /run/aegis/proxy.pid --signal STOP || true
for i in $(seq 1 20); do "${DC[@]}" exec -T aegis nft list table inet aegis >/dev/null 2>&1 || break; sleep 1; done
if "${DC[@]}" exec -T aegis nft list table inet aegis >/dev/null 2>&1; then echo watchdog-failed >&2; exit 1; fi
"${DC[@]}" exec -T client curl -fsS --max-time 5 "http://172.29.0.2:5000/crash-fail-open" >/dev/null
echo independent-watchdog-hung-proxy-fail-open-OK
echo integration-PASS
