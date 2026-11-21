import http.client
import re
import socket
import subprocess
from dataclasses import dataclass
@dataclass(frozen=True)
class Listener:
    address: str
    port: int

def listening_tcp():
    result = subprocess.run(["ss", "-Hlnpt", "-4"], capture_output=True, text=True, timeout=3, check=True)
    listeners = []
    for line in result.stdout.splitlines():
        columns = line.split()
        if len(columns) < 4: continue
        match = re.match(r"^(.+):(\d+)$", columns[3])
        if match:
            listeners.append(Listener(match.group(1).strip("[]"), int(match.group(2))))
    return listeners

def docker_published_tcp():
    try:
        result = subprocess.run(["docker", "ps", "--format", "{{.Ports}}"], capture_output=True, text=True, timeout=4, check=True)
    except (OSError, subprocess.SubprocessError):
        return []
    found = set()
    pattern = re.compile(r"(?:^|[, ]+)(?P<ip>(?:\d{1,3}\.){3}\d{1,3}|\*):(?P<host>\d+)->\d+/tcp")
    for line in result.stdout.splitlines():
        for match in pattern.finditer(line):
            found.add(Listener(match.group("ip"), int(match.group("host"))))
    return sorted(found, key=lambda x: (x.port, x.address))

def is_http(listener, timeout, excluded):
    if listener.port in excluded or listener.port < 1: return False
    host = listener.address if listener.address not in ("0.0.0.0", "*") else "127.0.0.1"
    conn = None
    try:
        conn = http.client.HTTPConnection(host, listener.port, timeout=timeout)
        conn.request("HEAD", "/", headers={"Host": "aegis-probe.invalid", "Connection": "close", "User-Agent": "Aegis-Discovery/1"})
        response = conn.getresponse(); response.read(4096)
        return 100 <= response.status <= 599
    except (OSError, http.client.HTTPException, socket.timeout): return False
    finally:
        if conn: conn.close()
