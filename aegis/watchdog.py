import os
import signal
import socket
import subprocess
import time
import yaml
from aegis import nft

def proxy_pid():
    pidfile = os.environ.get("AEGIS_PROXY_PIDFILE")
    if pidfile:
        try: return int(open(pidfile, encoding="utf-8").read().strip())
        except (OSError, ValueError): return 0
    result = subprocess.run(["systemctl", "show", "--property=MainPID", "--value", "aegis-proxy.service"], capture_output=True, text=True)
    try: return int(result.stdout.strip())
    except ValueError: return 0

def healthy(pid, port, heartbeat, timeout):
    if pid <= 1: return False
    try: os.kill(pid, 0)
    except OSError: return False
    try:
        beat_age = time.time() - os.stat(heartbeat).st_mtime
        if beat_age > timeout: return False
    except OSError:
        pidfile = os.environ.get("AEGIS_PROXY_PIDFILE")
        if not pidfile: return False
        try:
            if time.time() - os.stat(pidfile).st_mtime > max(12.0, timeout * 3): return False
            return True
        except OSError: return False
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5): return True
    except OSError: return False

def main():
    path = os.environ.get("AEGIS_CONFIG", "/etc/aegis/config.yaml")
    with open(path, encoding="utf-8") as stream: config = yaml.safe_load(stream)
    period = float(os.environ.get("AEGIS_WATCHDOG_INTERVAL", "2"))
    port = int(config["proxy"]["listen_port"])
    heartbeat = os.environ.get("AEGIS_HEARTBEAT", "/run/aegis/proxy.heartbeat")
    timeout = float(os.environ.get("AEGIS_WATCHDOG_TIMEOUT", "4"))
    loop = os.environ.get("AEGIS_WATCHDOG_LOOP", "0") == "1"
    while True:
        pid = proxy_pid()
        if not healthy(pid, port, heartbeat, timeout):
            nft.remove_table()
            if pid > 1:
                try: os.kill(pid, signal.SIGKILL)
                except OSError: pass
            print("watchdog: proxy unhealthy or stalled; removed only inet aegis table", flush=True)
        if not loop: return
        time.sleep(period)
if __name__ == "__main__": main()
