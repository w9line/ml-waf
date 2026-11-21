import argparse
import os
import time
import yaml
from aegis import discovery, nft

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="/etc/aegis/config.yaml")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    with open(args.config, encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    proxy = config["proxy"]
    settings = config["discovery"]
    excluded = set(settings.get("excluded_ports", [])) | {proxy["listen_port"]}
    while True:
        pidfile = os.environ.get("AEGIS_PROXY_PIDFILE")
        if pidfile:
            try: proxy_pid = int(open(pidfile, encoding="utf-8").read().strip())
            except (OSError, ValueError): proxy_pid = 0
            try: os.kill(proxy_pid, 0) if proxy_pid > 1 else (_ for _ in ()).throw(ProcessLookupError())
            except OSError:
                nft.remove_table()
                print("proxy missing; discovery exits fail-open", flush=True)
                return
            heartbeat = os.environ.get("AEGIS_HEARTBEAT", "/run/aegis/proxy.heartbeat")
            timeout = float(os.environ.get("AEGIS_WATCHDOG_TIMEOUT", "4"))
            try: beat_age = time.time() - os.stat(heartbeat).st_mtime
            except OSError:
                try: beat_age = time.time() - os.stat(pidfile).st_mtime
                except OSError: beat_age = 0
            if beat_age > timeout:
                nft.remove_table()
                print("proxy heartbeat stale; discovery exits fail-open", flush=True)
                return
        try:
            found = discovery.listening_tcp()
            if settings.get("docker_published_ports", True):
                found += discovery.docker_published_tcp()
            ports = {item.port for item in found if discovery.is_http(item, float(settings.get("probe_timeout_seconds", 0.4)), excluded)}
            ports.update(set(settings.get("include_ports", [])) - excluded)
            nft.ensure_table(proxy["listen_port"])
            nft.replace_ports(ports)
            print(f"Aegis HTTP listeners: {sorted(ports)}", flush=True)
        except Exception as error:
            print(f"Aegis update failed; retaining previous table: {error}", flush=True)
        if args.once:
            return
        time.sleep(max(1, int(settings.get("interval_seconds", 10))))

if __name__ == "__main__":
    main()
