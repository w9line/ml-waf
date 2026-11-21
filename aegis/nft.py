import subprocess
TABLE = "inet aegis"

def run(script):
    subprocess.run(["nft", "-f", "-"], input=script, text=True, check=True, timeout=5)

def ensure_table(proxy_port):
    exists = subprocess.run(["nft", "list", "table", *TABLE.split()], capture_output=True).returncode == 0
    if not exists:
        script = ("add table inet aegis\n"
                  "add set inet aegis http_ports { type inet_service; }\n"
                  "add chain inet aegis prerouting { type nat hook prerouting priority dstnat - 5; policy accept; }\n"
                  f"add rule inet aegis prerouting tcp dport @http_ports counter redirect to :{proxy_port}\n")
        run(script)

def replace_ports(ports):
    script = "flush set inet aegis http_ports\n"
    if ports:
        values = ", ".join(str(port) for port in sorted(ports))
        script += f"add element inet aegis http_ports {{ {values} }}\n"
    run(script)

def remove_table():
    subprocess.run(["nft", "delete", "table", "inet", "aegis"], capture_output=True, timeout=5)
