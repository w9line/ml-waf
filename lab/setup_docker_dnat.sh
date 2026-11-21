#!/usr/bin/env bash
set -euo pipefail
nft add table ip lab_docker_nat
nft 'add chain ip lab_docker_nat output { type nat hook output priority dstnat; policy accept; }'
nft add rule ip lab_docker_nat output ip daddr 172.29.0.2 tcp dport 15000 dnat to 172.29.0.2:5000
