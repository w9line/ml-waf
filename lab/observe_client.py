import json
from urllib.request import Request, ProxyHandler, build_opener

opener = build_opener(ProxyHandler({}))
base = "http://172.29.0.2:5000"
checks = [
    ("GET", "/observe?q=hello&page=1", None),
    ("GET", "/observe?q=HTTP+specification&page=2", None),
    ("GET", "/search?q=caf%C3%A9&page=3", None),
    ("POST", "/api/search?q=normal", json.dumps({"page": 4, "query": "ordinary API lookup"}).encode()),
    ("GET", "/docs?q=SQL+SELECT+examples&page=5", None),
]
for method, path, body in checks:
    headers = {"Content-Type": "application/json"} if body else {}
    req = Request(base + path, data=body, headers=headers, method=method)
    with opener.open(req, timeout=8) as response:
        assert response.status == 200, response.status
        item = json.loads(response.read())
        assert item["service"] == "flask" and item["method"] == method
        assert item["path"] == path.split("?", 1)[0]
print(f"observe lab backend responses verified: {len(checks)}")
