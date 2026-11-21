#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ $(id -u) -ne 0 ]]; then echo "Run as root: sudo ./run.sh" >&2; exit 1; fi
if [[ ! -x /opt/aegis/venv/bin/mitmdump ]]; then "$ROOT/install.sh"; fi
MODEL_TO_FETCH=$(/opt/aegis/venv/bin/python -c 'import pathlib,yaml; d=yaml.safe_load(open("/etc/aegis/config.yaml")) or {}; s=d.get("detector",{}); n={"Fizcko/argus_sentinel":"model.onnx","khasinski/ai-bouncer":"embedding_model.onnx","sdmlai/cyber-jev":"model.int8.onnx"}.get(s.get("model"),"missing.model"); print(s.get("model","") if s.get("mode")=="observe-only" and not (pathlib.Path(s.get("model_path",""))/n).is_file() else "")')
if [[ -n "$MODEL_TO_FETCH" ]]; then AEGIS_INSTALL_ROOT=/opt/aegis /opt/aegis/models/get_weights.sh "$MODEL_TO_FETCH"; fi
systemctl start aegis-proxy.service aegis-discovery.service aegis-watchdog.timer
systemctl --no-pager --full status aegis-proxy.service
