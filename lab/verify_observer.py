import json
import time
from pathlib import Path

path = Path("/run/aegis/telemetry.jsonl")
deadline = time.monotonic() + 30
records = []
while time.monotonic() < deadline:
    if path.exists():
        try:
            records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        except (OSError, json.JSONDecodeError):
            records = []
    observed = [row for row in records if row.get("model") == "sdmlai/cyber-jev" and row.get("mode") == "observe-only"]
    if len(observed) >= 5:
        break
    time.sleep(0.25)
else:
    raise SystemExit(f"observer telemetry missing: total_rows={len(records)}")
for row in observed[-5:]:
    assert row["label"] in {"benign", "malicious"}, row
    assert 0.0 <= float(row["score"]) <= 1.0, row
    assert float(row["latency_ms"]) > 0, row
    assert row.get("host_header") and row.get("dst") is not None, row
    assert "body" not in row and "request" not in row, row
print(json.dumps({"observe_only_rows": len(observed), "last_five_labels": [r["label"] for r in observed[-5:]], "last_five_scores": [round(float(r["score"]), 6) for r in observed[-5:]], "mean_inference_ms": round(sum(float(r["latency_ms"]) for r in observed[-5:]) / 5, 3)}))
