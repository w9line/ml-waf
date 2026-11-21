#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
INSTALL_ROOT=${AEGIS_INSTALL_ROOT:-$(cd -- "$SCRIPT_DIR/.." && pwd)}
MODEL=${1:-}
case "$MODEL" in
  Fizcko/argus_sentinel) ASSET=argus_sentinel; FOLDER=Fizcko--argus_sentinel; REV=59848dd563bf2f8e7e0543f126894e00be6d5a02 ;;
  khasinski/ai-bouncer) ASSET=ai_bouncer; FOLDER=khasinski--ai-bouncer; REV=5b25bae8367498cd276606369b8186a7862bd60f ;;
  sdmlai/cyber-jev) ASSET=cyber_jev; FOLDER=sdmlai--cyber-jev; REV=3fea0b1ec86ac3efd9d1352d5f1e4008cc0c17b7 ;;
  *) echo "Usage: $0 {Fizcko/argus_sentinel|khasinski/ai-bouncer|sdmlai/cyber-jev}" >&2; exit 2 ;;
esac
RELEASE=https://github.com/w9line/ml-waf/releases/download/v0.1.0
for tool in curl sha256sum tar; do command -v "$tool" >/dev/null || { echo "Missing required tool: $tool" >&2; exit 1; }; done
TMP_BASE=${TMPDIR:-$HOME/.cache}
mkdir -p "$TMP_BASE"
TMP=$(mktemp -d "$TMP_BASE/aegis-weights.XXXXXX")
trap "rm -rf -- \"$TMP\"" EXIT
curl -fL --retry 3 "$RELEASE/${ASSET}.tar.gz" -o "$TMP/${ASSET}.tar.gz"
curl -fL --retry 3 "$RELEASE/${ASSET}.SHA256" -o "$TMP/${ASSET}.SHA256"
(cd "$TMP" && sha256sum -c "${ASSET}.SHA256")
mkdir -p "$INSTALL_ROOT"
tar -xzf "$TMP/${ASSET}.tar.gz" -C "$INSTALL_ROOT" "models/weights/${FOLDER}/${REV}" "models/ATTRIBUTION.md"
echo "Pinned $MODEL weights installed under $INSTALL_ROOT/models/weights/$FOLDER/$REV"
