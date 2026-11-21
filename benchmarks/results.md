# Offline model benchmark results

Run: 2026-11-21 01:57 UTC. Exactly the three requested repositories were evaluated; no card metrics were reused.

## Primary table

| Model | Size MB | FPR | Recall | F1 | p95 ms | RAM MB |
|---|---:|---:|---:|---:|---:|---:|
| Fizcko/argus_sentinel | 5.23 | 0.004 | 0.048 | 0.092 | 0.378 | 86.680 |
| khasinski/ai-bouncer | 34.37 | 0.571 | 0.977 | 0.767 | 0.668 | 125.898 |
| sdmlai/cyber-jev | 23.73 | 0.013 | 0.919 | 0.951 | 38.390 | 177.523 |

Primary metrics use the MicroData-derived held-out test split. For models with meaningful continuous threat scores, thresholds were selected only on the separate validation split with a 1% validation-FPR cap. AiBouncer exposes a categorical label, not an attack probability, so it is evaluated at its native label decision without threshold fitting. RAM is process RSS after model load; size is downloaded runtime files.

## Dataset and leakage notes

- CSIC 2010: pinned public `bridge4/CSIC2010_dataset_classification` test split. Original labels retained as 0 benign / 1 anomalous. Up to 2,000 per class after global exact-text de-duplication. This is descriptive only for AiBouncer and Cyber-Jev because their published training data explicitly includes CSIC2010; CSIC metrics are not used for threshold selection or the primary table.
- Secondary test: pinned `neuroX3/MicroData` test split. Only sources `synthetic`, `synthetic_heavy_control`, and `synthetic_heavy_polymorphic` are included; known `ai-waf-dataset` and `payloadsallthethings` overlaps are excluded. Up to 2,000 per class, seed 42; 20% validation / 80% held-out. Exact synthetic-template overlap with model training is not documented, so residual leakage risk remains.
- Additional benign-only set: manually curated, non-secret HTTP requests for JSON APIs, curl, Python urllib, Unicode, and technical searches. It is evaluated separately and retained even when a model flags it.
- All models receive identical canonical examples per split. Raw request text is not written to result files. Weights are pinned to immutable revisions.
- Sample counts: `{"CSIC2010_available": 18500, "CSIC2010_sample": 4000, "MicroData_nonoverlap_source_available": 75413, "MicroData_sources": {"synthetic": 2827, "synthetic_heavy_control": 541, "synthetic_heavy_polymorphic": 632}, "MicroData_test": 3200, "MicroData_validation": 800, "cross_label_duplicates_removed": 0, "curated_benign": 250, "exact_duplicate_rows_removed": 8544}`

## Confusion matrices and scores

Confusion matrix order is `[[TN, FP], [FN, TP]]`. Fitted thresholds use validation only.

### Fizcko/argus_sentinel
Revision `59848dd563bf2f8e7e0543f126894e00be6d5a02`; license `Apache-2.0`; threshold `0.740463 (validation_selected_score)`.
- Primary held-out: `[[1594, 6], [1523, 77]]`; precision 0.928, recall 0.048, FPR 0.004, FNR 0.952, F1 0.092.
- CSIC2010 (overlap-contaminated descriptive only): `[[2000, 0], [2000, 0]]`; precision 0.000, recall 0.000, FPR 0.000, FNR 1.000, F1 0.000.
- Aggregated false-positive categories (tags can overlap; no payloads recorded): primary `{"curl_user_agent": 2, "technical_search": 6}`; CSIC `{}`; curated benign `{}`.
- CPU p50/p95/p99 ms: preprocessing 0.042/0.089/0.142; inference 0.259/0.280/0.370; end-to-end 0.302/0.378/0.462.
- Load 50.62 ms; single-thread throughput 3191.68 requests/s; RSS 86.68 MB; peak RSS 363.21 MB.

### khasinski/ai-bouncer
Revision `5b25bae8367498cd276606369b8186a7862bd60f`; license `MIT`; threshold `0.500000 (native_categorical_label)`.
- Primary held-out: `[[687, 913], [37, 1563]]`; precision 0.631, recall 0.977, FPR 0.571, FNR 0.023, F1 0.767.
- CSIC2010 (overlap-contaminated descriptive only): `[[55, 1945], [19, 1981]]`; precision 0.505, recall 0.991, FPR 0.973, FNR 0.009, F1 0.669.
- Aggregated false-positive categories (tags can overlap; no payloads recorded): primary `{"curl_user_agent": 254, "technical_search": 913}`; CSIC `{"csic2010_webshop": 1945, "technical_search": 1945}`; curated benign `{"curl_user_agent": 50, "json_api": 16, "python_urllib_user_agent": 50, "technical_search": 50, "unicode_search": 50}`.
- CPU p50/p95/p99 ms: preprocessing 0.159/0.255/0.329; inference 0.292/0.421/0.542; end-to-end 0.453/0.668/0.869.
- Load 98.60 ms; single-thread throughput 2135.26 requests/s; RSS 125.90 MB; peak RSS 363.21 MB.

### sdmlai/cyber-jev
Revision `3fea0b1ec86ac3efd9d1352d5f1e4008cc0c17b7`; license `CC-BY-NC-4.0`; threshold `0.962627 (validation_selected_score)`.
- Primary held-out: `[[1580, 20], [130, 1470]]`; precision 0.987, recall 0.919, FPR 0.013, FNR 0.081, F1 0.951.
- CSIC2010 (overlap-contaminated descriptive only): `[[1859, 141], [835, 1165]]`; precision 0.892, recall 0.583, FPR 0.070, FNR 0.417, F1 0.705.
- Aggregated false-positive categories (tags can overlap; no payloads recorded): primary `{"curl_user_agent": 10, "technical_search": 20}`; CSIC `{"csic2010_webshop": 141, "technical_search": 141}`; curated benign `{}`.
- CPU p50/p95/p99 ms: preprocessing 0.432/0.558/0.978; inference 34.072/37.877/74.892; end-to-end 34.515/38.390/75.904.
- Load 770.21 ms; single-thread throughput 28.01 requests/s; RSS 177.52 MB; peak RSS 363.21 MB.

## Decision

Block mode remains off. The primary decision uses out-of-domain benign FPR first, then CPU latency, then useful recall. If all three fail the normal-traffic FPR bar, report no selected model; an observe-only adapter does not imply a safe blocking model.

## Reproducibility

- Seed 42; max 2,000 benign and 2,000 malicious per source; exact duplicates removed before sampling.
- CPUExecutionProvider, one ONNX intra-op thread, separate process per candidate, up to 40 fixed validation examples for warmup.
- `benchmarks/run.sh --offline` runs from cached weights and Parquet data with Docker networking disabled. The first non-offline run fetches the pinned public assets.
