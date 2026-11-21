from __future__ import annotations
import argparse
import json
import math
import os
import resource
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
BENCH = ROOT / "benchmarks"
DATA_CACHE = BENCH / "data" / "datasets"
CATALOG = json.loads((BENCH / "model_catalog.json").read_text())
TARGET_FPR = 0.01

def confusion(labels, scores, threshold):
    tp=fp=tn=fn=0
    for y,s in zip(labels,scores):
        pred=int(float(s)>=float(threshold))
        if y==1 and pred: tp+=1
        elif y==0 and pred: fp+=1
        elif y==0: tn+=1
        else: fn+=1
    precision=tp/(tp+fp) if tp+fp else 0.0
    recall=tp/(tp+fn) if tp+fn else 0.0
    f1=2*precision*recall/(precision+recall) if precision+recall else 0.0
    fpr=fp/(fp+tn) if fp+tn else 0.0
    fnr=fn/(fn+tp) if fn+tp else 0.0
    return {"tp":tp,"fp":fp,"tn":tn,"fn":fn,"precision":precision,"recall":recall,"f1":f1,"fpr":fpr,"fnr":fnr}

def choose_threshold(labels, scores, max_fpr=TARGET_FPR):
    candidates=sorted(set([float(x) for x in scores]+[0.0,1.000001]))
    feasible=[]
    for th in candidates:
        m=confusion(labels,scores,th)
        if m["fpr"]<=max_fpr: feasible.append((m["recall"],-m["fpr"],th,m))
    if not feasible: return 1.000001,confusion(labels,scores,1.000001)
    recall,neg_fpr,th,m=max(feasible,key=lambda x:(x[0],x[1],x[2]))
    return th,m

def percentiles(values):
    if not values:return {"p50":0.0,"p95":0.0,"p99":0.0}
    v=sorted(float(x) for x in values)
    def at(q): return round(v[min(len(v)-1,int((len(v)-1)*q))],4)
    return {"p50":at(.50),"p95":at(.95),"p99":at(.99)}

def measure(adapter, rows):
    scores=[]; raw=[]; prep=[]; infer=[]; total=[]; start=time.perf_counter()
    for sample in rows:
        result=adapter.predict(sample)
        scores.append(float(result["score"])); raw.append(str(result.get("raw_label","")))
        prep.append(float(result["preprocess_ms"])); infer.append(float(result["inference_ms"])); total.append(float(result["latency_ms"]))
    elapsed=time.perf_counter()-start
    return {"scores":scores,"raw_labels":raw,"preprocess_ms":percentiles(prep),"inference_ms":percentiles(infer),"total_ms":percentiles(total),"rps":len(rows)/elapsed if elapsed else 0.0,"elapsed_s":elapsed}

def worker(model_name, model_path):
    import gc
    import psutil
    from aegis.model_backends import ADAPTERS
    samples=json.load(sys.stdin)
    model_meta=next(x for x in CATALOG["models"] if x["name"]==model_name)
    size=sum(p.stat().st_size for p in Path(model_path).iterdir() if p.is_file() and p.name!="aegis_manifest.json")
    rss_before=psutil.Process().memory_info().rss/1048576
    t0=time.perf_counter(); adapter=ADAPTERS[model_name](Path(model_path)); load_ms=(time.perf_counter()-t0)*1000
    # Fixed warm-up examples, identical between candidates and not included in metrics.
    for sample in samples["validation"][:40]: adapter.predict(sample)
    rss_loaded=psutil.Process().memory_info().rss/1048576
    val=measure(adapter,samples["validation"]); thresholdable=getattr(adapter,"thresholdable",True)
    if thresholdable: threshold,val_metrics=choose_threshold([x["label"] for x in samples["validation"]],val["scores"])
    else: threshold=0.5; val_metrics=confusion([x["label"] for x in samples["validation"]],val["scores"],threshold)
    test=measure(adapter,samples["test"]); csic=measure(adapter,samples["csic2010"]); curated=measure(adapter,samples["curated_benign"])
    test_metrics=confusion([x["label"] for x in samples["test"]],test["scores"],threshold)
    csic_metrics=confusion([x["label"] for x in samples["csic2010"]],csic["scores"],threshold)
    curated_metrics=confusion([x["label"] for x in samples["curated_benign"]],curated["scores"],threshold)
    def fp_category_counts(rows, measured):
        counts={}
        for row,score in zip(rows,measured["scores"]):
            if row["label"]!=0 or score<threshold: continue
            cats=row.get("categories") or [row.get("category") or row.get("dataset","uncategorized")]
            for cat in cats: counts[cat]=counts.get(cat,0)+1
        return counts
    test_fp_categories=fp_category_counts(samples["test"],test)
    csic_fp_categories=fp_category_counts(samples["csic2010"],csic)
    curated_fp_categories=fp_category_counts(samples["curated_benign"],curated)
    peak_rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024.0
    record={
        "name":model_name,"status":"OK","revision":model_meta["revision"],"license":model_meta["license"],"size_bytes":size,
        "load_ms":load_ms,"rss_before_mb":rss_before,"rss_loaded_mb":rss_loaded,"peak_rss_mb":peak_rss,
        "threshold_target_fpr":TARGET_FPR,"threshold":threshold,"threshold_mode":"validation_selected_score" if thresholdable else "native_categorical_label",
        "validation":val_metrics,"test":test_metrics,"csic2010":csic_metrics,"curated_benign":curated_metrics,
        "test_false_positive_categories":test_fp_categories,"csic_false_positive_categories":csic_fp_categories,"curated_false_positive_categories":curated_fp_categories,
        "latency":{"validation":val["total_ms"],"test_total":test["total_ms"],"test_preprocess":test["preprocess_ms"],"test_inference":test["inference_ms"],"csic_total":csic["total_ms"],"curated_total":curated["total_ms"]},
        "rps_single_thread":test["rps"],"test_elapsed_s":test["elapsed_s"],
        "tested_counts":{"validation":len(samples["validation"]),"test":len(samples["test"]),"csic2010":len(samples["csic2010"]),"curated_benign":len(samples["curated_benign"])}
    }
    print(json.dumps(record,ensure_ascii=False))
    del adapter; gc.collect()

def run_worker(model_name, model_path, samples):
    cmd=[sys.executable,str(Path(__file__).resolve()),"--worker",model_name,"--model-path",str(model_path)]
    env=os.environ.copy();env.update({"OMP_NUM_THREADS":"1","MKL_NUM_THREADS":"1","OPENBLAS_NUM_THREADS":"1","TRANSFORMERS_VERBOSITY":"error","TOKENIZERS_PARALLELISM":"false"})
    proc=subprocess.run(cmd,input=json.dumps(samples,ensure_ascii=False),text=True,capture_output=True,env=env,timeout=1800)
    if proc.returncode:
        detail=(proc.stderr or proc.stdout)[-3000:]
        return {"name":model_name,"status":"SKIP","reason":detail.strip() or f"worker exit {proc.returncode}"}
    lines=[x for x in proc.stdout.splitlines() if x.strip()]
    try:return json.loads(lines[-1])
    except Exception as exc:return {"name":model_name,"status":"SKIP","reason":f"worker returned invalid JSON: {exc}; {proc.stdout[-1000:]}"}

def _fmt(value,digits=3):
    if value is None:return "—"
    if isinstance(value,str):return value
    return f"{value:.{digits}f}"

def render_markdown(results, counts):
    date=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out=["# Offline model benchmark results", "", f"Run: {date}. Exactly the three requested repositories were evaluated; no card metrics were reused.", "", "## Primary table", "", "| Model | Size MB | FPR | Recall | F1 | p95 ms | RAM MB |", "|---|---:|---:|---:|---:|---:|---:|"]
    for r in results:
        if r["status"] != "OK": out.append(f"| {r['name']} (SKIP) | — | — | — | — | — | — |")
        else: out.append(f"| {r['name']} | {_fmt(r['size_bytes']/1e6,2)} | {_fmt(r['test']['fpr'])} | {_fmt(r['test']['recall'])} | {_fmt(r['test']['f1'])} | {_fmt(r['latency']['test_total']['p95'])} | {_fmt(r['rss_loaded_mb'])} |")
    out += ["", "Primary metrics use the MicroData-derived held-out test split. For models with meaningful continuous threat scores, thresholds were selected only on the separate validation split with a 1% validation-FPR cap. AiBouncer exposes a categorical label, not an attack probability, so it is evaluated at its native label decision without threshold fitting. RAM is process RSS after model load; size is downloaded runtime files.", "", "## Dataset and leakage notes", "", "- CSIC 2010: pinned public `bridge4/CSIC2010_dataset_classification` test split. Original labels retained as 0 benign / 1 anomalous. Up to 2,000 per class after global exact-text de-duplication. This is descriptive only for AiBouncer and Cyber-Jev because their published training data explicitly includes CSIC2010; CSIC metrics are not used for threshold selection or the primary table.", "- Secondary test: pinned `neuroX3/MicroData` test split. Only sources `synthetic`, `synthetic_heavy_control`, and `synthetic_heavy_polymorphic` are included; known `ai-waf-dataset` and `payloadsallthethings` overlaps are excluded. Up to 2,000 per class, seed 42; 20% validation / 80% held-out. Exact synthetic-template overlap with model training is not documented, so residual leakage risk remains.", "- Additional benign-only set: manually curated, non-secret HTTP requests for JSON APIs, curl, Python urllib, Unicode, and technical searches. It is evaluated separately and retained even when a model flags it.", "- All models receive identical canonical examples per split. Raw request text is not written to result files. Weights are pinned to immutable revisions.", f"- Sample counts: `{json.dumps(counts,sort_keys=True)}`", "", "## Confusion matrices and scores", "", "Confusion matrix order is `[[TN, FP], [FN, TP]]`. Fitted thresholds use validation only."]
    for r in results:
        out += ["", f"### {r['name']}"]
        if r["status"] != "OK":
            out += ["", f"SKIP: {r.get('reason','no details')}"]
            continue
        threshold_text = f"{_fmt(r['threshold'],6)} ({r['threshold_mode']})"
        out.append(f"Revision `{r['revision']}`; license `{r['license']}`; threshold `{threshold_text}`.")
        for key,title in (("test","Primary held-out"),("csic2010","CSIC2010 (overlap-contaminated descriptive only)")):
            m=r[key]
            out.append(f"- {title}: `[[{m['tn']}, {m['fp']}], [{m['fn']}, {m['tp']}]]`; precision {_fmt(m['precision'])}, recall {_fmt(m['recall'])}, FPR {_fmt(m['fpr'])}, FNR {_fmt(m['fnr'])}, F1 {_fmt(m['f1'])}.")
        out.append(f"- Aggregated false-positive categories (tags can overlap; no payloads recorded): primary `{json.dumps(r['test_false_positive_categories'],sort_keys=True)}`; CSIC `{json.dumps(r['csic_false_positive_categories'],sort_keys=True)}`; curated benign `{json.dumps(r['curated_false_positive_categories'],sort_keys=True)}`.")
        pre=r['latency']['test_preprocess']; inf=r['latency']['test_inference']; total=r['latency']['test_total']
        out.append(f"- CPU p50/p95/p99 ms: preprocessing {_fmt(pre['p50'])}/{_fmt(pre['p95'])}/{_fmt(pre['p99'])}; inference {_fmt(inf['p50'])}/{_fmt(inf['p95'])}/{_fmt(inf['p99'])}; end-to-end {_fmt(total['p50'])}/{_fmt(total['p95'])}/{_fmt(total['p99'])}.")
        out.append(f"- Load {_fmt(r['load_ms'],2)} ms; single-thread throughput {_fmt(r['rps_single_thread'],2)} requests/s; RSS {_fmt(r['rss_loaded_mb'],2)} MB; peak RSS {_fmt(r['peak_rss_mb'],2)} MB.")
    out += ["", "## Decision", "", "Block mode remains off. The primary decision uses out-of-domain benign FPR first, then CPU latency, then useful recall. If all three fail the normal-traffic FPR bar, report no selected model; an observe-only adapter does not imply a safe blocking model.", "", "## Reproducibility", "", "- Seed 42; max 2,000 benign and 2,000 malicious per source; exact duplicates removed before sampling.", "- CPUExecutionProvider, one ONNX intra-op thread, separate process per candidate, up to 40 fixed validation examples for warmup.", "- `benchmarks/run.sh --offline` runs from cached weights and Parquet data with Docker networking disabled. The first non-offline run fetches the pinned public assets.", ""]
    return "\n".join(out)

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--offline",action="store_true");parser.add_argument("--worker",choices=[x["name"] for x in CATALOG["models"]]);parser.add_argument("--model-path");args=parser.parse_args()
    if args.worker:
        worker(args.worker,args.model_path);return
    from data import prepare_splits,download_model_files
    DATA_CACHE.mkdir(parents=True,exist_ok=True)
    samples=prepare_splits(DATA_CACHE,offline=args.offline)
    results=[]
    for model in CATALOG["models"]:
        try:
            folder=download_model_files(model,offline=args.offline)
            result=run_worker(model["name"],folder,samples)
        except Exception as exc: result={"name":model["name"],"status":"SKIP","reason":f"{type(exc).__name__}: {exc}"}
        results.append(result);print(model["name"],result.get("status"),flush=True)
    (BENCH/"results.json").write_text(json.dumps({"seed":42,"counts":samples["counts"],"results":results},indent=2,ensure_ascii=False))
    (BENCH/"results.md").write_text(render_markdown(results,samples["counts"]))
    print(f"Wrote {BENCH/'results.md'}")
    for result in results:
        if result["status"]=="SKIP":print("SKIP",result["name"],result.get("reason",""))

if __name__=="__main__":main()
