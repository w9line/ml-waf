from __future__ import annotations
import base64
import hashlib
import json
import random
import urllib.request
from collections import Counter
from pathlib import Path
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / "benchmarks/model_catalog.json").read_text())
CACHE_ROOT = ROOT / "models" / "weights"
SEED = 42
CAP_PER_CLASS = 2000
MICRO_ALLOWED = set(CATALOG["datasets"]["microdata"]["allowed_sources"])

def _get(url: str, dest: Path, offline: bool = False) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size:
        return
    if offline: raise FileNotFoundError(f"offline mode: missing cached file {dest}")
    req = urllib.request.Request(url, headers={"User-Agent": "AegisOfflineBenchmark/1.0"})
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(req, timeout=90) as response, tmp.open("wb") as out:
        while chunk := response.read(1024 * 1024): out.write(chunk)
    tmp.replace(dest)

def download_model_files(model: dict, offline: bool = False) -> Path:
    folder = CACHE_ROOT / model["repo_id"].replace("/", "--") / model["revision"]
    repo_id = model["repo_id"]; revision = model["revision"]
    for name in model["files"]:
        url = f"https://huggingface.co/{repo_id}/resolve/{revision}/{name}?download=true"
        _get(url, folder / name, offline=offline)
    (folder / "aegis_manifest.json").write_text(json.dumps({"repo_id": model["repo_id"], "revision": model["revision"], "license": model["license"], "files": model["files"]}, indent=2))
    return folder

def _read_parquet(path: Path) -> list[dict]:
    return pq.read_table(path).to_pylist()

def _normal_key(text: str) -> str:
    normalized = text.replace(chr(92) + "r" + chr(92) + "n", "\n").replace(chr(92) + "n", "\n").replace(chr(92) + "r", "\n").replace("\r\n", "\n").replace("\r", "\n").strip()
    return hashlib.sha256(normalized.encode("utf-8", "replace")).hexdigest()

def _request_categories(text: str, source: str, label: int) -> list[str]:
    if label == 1: return []
    normalized = text.replace(chr(92) + "n", "\n").replace("\r\n", "\n").lower()
    tags = []
    if "user-agent: curl" in normalized: tags.append("curl_user_agent")
    if "user-agent: python-urllib" in normalized: tags.append("python_urllib_user_agent")
    if "content-type: application/json" in normalized or "{\"query\"" in normalized: tags.append("json_api")
    if any(ord(ch) > 127 for ch in text): tags.append("unicode")
    if any(term in normalized for term in ("sql", "select", "http", "urllib", "documentation", "specification", "curl")): tags.append("technical_search")
    if source == "csic2010": tags.append("csic2010_webshop")
    return list(dict.fromkeys(tags or ["other_benign"]))

def _row(text: str, original_label: int, source: str, family: str, source_dataset: str, category: str = "") -> dict:
    categories = [category] if category else _request_categories(text, source, int(original_label))
    return {"request": text, "original_label": int(original_label), "label": int(original_label), "source": source, "family": family, "dataset": source_dataset, "category": category, "categories": categories, "request_sha256": _normal_key(text)}

def _stratified_cap(rows: list[dict], cap: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    out = []
    for label in (0, 1):
        group = [r for r in rows if r["label"] == label]
        group.sort(key=lambda r: r["request_sha256"])
        rng.shuffle(group)
        out.extend(group[:cap])
    return out

def _make_request(method: str, path: str, host: str, ua: str, body: str, content_type: str, category: str, index: int) -> dict:
    headers = [f"Host: {host}", f"User-Agent: {ua}", "Accept: application/json, text/plain, */*"]
    if content_type: headers.append(f"Content-Type: {content_type}")
    body_len = len(body.encode("utf-8"))
    if body: headers.append(f"Content-Length: {body_len}")
    raw = f"{method} {path} HTTP/1.1\r\n" + "\r\n".join(headers) + "\r\n\r\n" + body
    return {"request": raw, "original_label": 0, "label": 0, "source": "manual_curated", "family": "benign", "dataset": "curated-benign-v1", "category": category, "categories": [category], "request_sha256": _normal_key(raw), "sample_id": f"{category}-{index:03d}"}

def curated_benign() -> list[dict]:
    rows = []
    terms = ["pricing guide", "Unicode normalization", "HTTP Content-Length specification", "SQL SELECT statement examples", "curl POST JSON documentation", "Python urllib Request headers", "database index query planner", "UTF-8 characters café 東京", "REST API pagination", "JSON schema validation"]
    unicode_terms = ["café menu", "東京 weather", "naïve bayes notes", "Straße und Wörter", "emoji 😀 API", "中文搜索", "crème brûlée", "München Straße", "Español información", "Καλημέρα κόσμε"]
    for i in range(50):
        term = terms[i % len(terms)]
        n = i + 1
        body = json.dumps({"query": term, "page": n, "filters": {"active": True}, "sort": "name"}, ensure_ascii=False, separators=(",", ":"))
        rows.append(_make_request("POST", f"/api/v1/search?page={n}", "api.example.test", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/122.0", body, "application/json", "json_api", n))
        rows.append(_make_request("GET", f"/docs/search?q={term.replace(chr(32), chr(43))}&page={n}", "docs.example.test", "curl/8.6.0", "", "", "curl_user_agent", n))
        rows.append(_make_request("GET", f"/api/search?q={term.replace(chr(32), chr(43))}&page={n}", "api.example.test", "Python-urllib/3.13", "", "", "python_urllib_user_agent", n))
        uterm = unicode_terms[i % len(unicode_terms)]
        rows.append(_make_request("GET", f"/search?q={uterm}&page={n}", "search.example.test", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/122.0", "", "", "unicode_search", n))
        tech = terms[(i + 3) % len(terms)]
        rows.append(_make_request("GET", f"/knowledge/search?q={tech.replace(chr(32), chr(43))}&page={n}", "kb.example.test", "curl/8.6.0", "", "", "technical_search", n))
    unique = {}
    for row in rows: unique.setdefault(row["request_sha256"], row)
    return list(unique.values())

def load_raw_splits(temp_root: Path, offline: bool = False) -> dict:
    catalog = CATALOG["datasets"]
    csic = catalog["csic2010"]
    micro = catalog["microdata"]
    csic_path = temp_root / "csic2010" / Path(csic["test_file"]).name
    url_csic = f"https://huggingface.co/datasets/{csic['repo_id']}/resolve/{csic['revision']}/{csic['test_file']}?download=true"
    _get(url_csic, csic_path, offline=offline)
    csic_rows = []
    for r in _read_parquet(csic_path):
        text = r.get("requests") or ""
        if text: csic_rows.append(_row(text, int(r["label"]), "csic2010", "attack" if int(r["label"]) else "benign", "CSIC2010"))
    micro_rows = []
    for part in micro["test_files"]:
        f = temp_root / "microdata" / Path(part).name
        url_micro = f"https://huggingface.co/datasets/{micro['repo_id']}/resolve/{micro['revision']}/{part}?download=true"
        _get(url_micro, f, offline=offline)
        for r in _read_parquet(f):
            source = str(r.get("source", "unknown"))
            if source not in MICRO_ALLOWED: continue
            try: raw = base64.b64decode(r["raw_bytes_b64"], validate=True).decode("utf-8", "replace")
            except (ValueError, KeyError, TypeError): continue
            label = int(r["label"])
            micro_rows.append(_row(raw, label, source, str(r.get("family", "unknown")), "MicroData"))
    return {"csic_rows": csic_rows, "micro_rows": micro_rows}

def prepare_splits(temp_root: Path, offline: bool = False) -> dict:
    rng = random.Random(SEED)
    raw = load_raw_splits(temp_root, offline=offline)
    # Drop conflicting duplicate payloads and exact duplicates before any sampling.
    chosen = {}
    conflicts = set()
    exact_duplicate_rows_removed = 0
    for group_name in ("micro_rows", "csic_rows"):
        for row in raw[group_name]:
            key = row["request_sha256"]
            prior = chosen.get(key)
            if prior is not None and prior["label"] != row["label"]:
                conflicts.add(key)
            elif prior is None:
                chosen[key] = row
            else:
                exact_duplicate_rows_removed += 1
    for key in conflicts: chosen.pop(key, None)
    micro_rows = [r for r in chosen.values() if r["dataset"] == "MicroData"]
    csic_rows = [r for r in chosen.values() if r["dataset"] == "CSIC2010"]
    micro = _stratified_cap(micro_rows, CAP_PER_CLASS, SEED)
    # Hold out 20% per class for threshold selection, retain the rest for final reporting.
    micro_val, micro_test = [], []
    for label in (0, 1):
        group = [r for r in micro if r["label"] == label]
        rng.shuffle(group)
        n_val = max(1, int(len(group) * 0.2)) if group else 0
        micro_val.extend(group[:n_val]); micro_test.extend(group[n_val:])
    csic = _stratified_cap(csic_rows, CAP_PER_CLASS, SEED + 1)
    curated = curated_benign()
    return {"validation": micro_val, "test": micro_test, "csic2010": csic, "curated_benign": curated,
            "counts": {"CSIC2010_available": len(csic_rows), "MicroData_nonoverlap_source_available": len(micro_rows), "exact_duplicate_rows_removed": exact_duplicate_rows_removed, "cross_label_duplicates_removed": len(conflicts), "CSIC2010_sample": len(csic), "MicroData_validation": len(micro_val), "MicroData_test": len(micro_test), "curated_benign": len(curated), "MicroData_sources": dict(Counter(r["source"] for r in micro))}}
