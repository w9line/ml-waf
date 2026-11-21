import json
from pathlib import Path
rows=[json.loads(x) for x in Path("/run/aegis/telemetry.jsonl").read_text().splitlines() if x.strip()]
row=next((x for x in rows if x.get("path")=="/path"),None)
assert row is not None, rows
assert row["dst"]==["172.29.0.2",15000], row
assert row["host_header"]=="proof.internal", row
assert row["label"]=="benign", row
print(json.dumps({"original_published_destination":row["dst"],"host_header":row["host_header"],"proxy_label":row["label"],"nft_redirect":"verified"}))
