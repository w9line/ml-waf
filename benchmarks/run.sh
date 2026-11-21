#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
docker build --network host -f benchmarks/Dockerfile -t aegis-offline-benchmark:local .
NET=host
if [[ "${1:-}" == "--offline" ]]; then NET=none; fi
exec docker run --rm --cpus=1 --network "$NET" -v "$ROOT:/work" -w /work aegis-offline-benchmark:local "$@"
