import os
import socket
import sys
import time

def main():
    port = int(os.environ.get("AEGIS_PROXY_PORT", "18080"))
    heartbeat = os.environ.get("AEGIS_HEARTBEAT", "/run/aegis/proxy.heartbeat")
    deadline = time.monotonic() + float(os.environ.get("AEGIS_START_TIMEOUT", "20"))
    while time.monotonic() < deadline:
        try: fresh = time.time() - os.stat(heartbeat).st_mtime < 2.0
        except OSError: fresh = False
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5): listening = True
        except OSError: listening = False
        if fresh and listening:
            print("Aegis proxy listener and event-loop heartbeat are healthy", flush=True)
            return 0
        time.sleep(0.2)
    print("Aegis proxy failed startup health check", file=sys.stderr)
    return 1
if __name__ == "__main__": raise SystemExit(main())
