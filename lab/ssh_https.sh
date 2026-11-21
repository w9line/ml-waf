#!/usr/bin/env bash
set -euo pipefail
mkdir -p /run/sshd
ssh-keygen -A
openssl req -x509 -newkey rsa:2048 -nodes -keyout /opt/aegis/lab/server.key -out /opt/aegis/lab/server.crt -subj /CN=aegis-lab -days 1 >/dev/null 2>&1
/usr/sbin/sshd -p 2222
exec nginx -c /opt/aegis/lab/nginx.conf -g "daemon off;"
