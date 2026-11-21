#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/.."
python3 -c "from aegis.detector import AllowAllDetector, detector_from_config; r=AllowAllDetector().predict(None); assert r[\"label\"] == \"benign\" and r[\"score\"] == 0.0 and r[\"latency_ms\"] == 0.0; assert isinstance(detector_from_config({\"mode\": \"allow-all\"}), AllowAllDetector)"
python3 -m compileall -q aegis
echo "smoke passed"
