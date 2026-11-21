# Aegis network integration results

Recorded from a real `./tests/integration.sh` run in the isolated Docker bridge lab on 2026-11-21 UTC. Each arm issued 1,000 GETs at concurrency 50 to the Flask backend. No model inference was enabled.

| Path | Successful | RPS | p50 ms | p95 ms | p99 ms | elapsed s |
|---|---:|---:|---:|---:|---:|---:|
| Direct backend (`127.0.0.1:5000`) | 1000 | 2099.29 | 22.448 | 25.336 | 26.040 | 0.476 |
| Transparent Aegis (lab client to `172.29.0.2:5000`) | 1000 | 438.64 | 109.088 | 138.471 | 140.099 | 2.280 |

Post-load `docker stats --no-stream` point-in-time snapshot: Aegis container 4.70% CPU and 83.55 MiB; app container 0.11% CPU and 42.06 MiB. These are not peak or per-request averages. Client max RSS was 37,144 KiB direct and 39,644 KiB via Aegis; client user CPU was 0.365 s and 0.341 s, respectively.

Verified by the same integration run:

- nftables redirect counters incremented; JSONL telemetry reported original destination `172.29.0.2:5000`.
- Flask GET preserved method, Host, path and query; JSON POST preserved body and query; FastAPI and NGINX requests passed.
- Two requests reused one HTTP/1.1 keep-alive connection.
- Listener :31337 started after Aegis and was later added to the nftables set by dynamic discovery.
- SSH :2222 and HTTPS :8443 succeeded without changing the redirect counter.
- `emergency-stop.sh` removed the Aegis table and a new client request reached the backend directly.
- SIGSTOP froze the proxy event loop; the independent heartbeat watchdog removed only the Aegis table and direct backend access recovered.
- An isolated nftables DNAT-equivalent fixture mapped a published-style :15000 target to Flask :5000 via the lab namespace OUTPUT chain. Aegis intercepted PREROUTING, telemetry retained original destination :15000, backend response passed, and the Aegis counter incremented. This validates the transparent routing shape without modifying host firewall rules; it is not a Docker-daemon port-publishing test.

The lab backends share a network namespace with Aegis so `ss` can discover them; the client is separate. Docker published-port discovery exists but is not yet independently tested with a Docker-in-Docker fixture.
