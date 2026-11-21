import json
rows=[json.loads(x) for x in open("/run/aegis/telemetry.jsonl")]
assert any(x["dst"]==["172.29.0.2",5000] for x in rows)
print("original destination verified; events=",len(rows))
