# Model artifacts

`models/weights/` is a local cache and is intentionally excluded from source commits. Each pinned model has its own versioned GitHub Release archive and SHA-256 sidecar; `get_weights.sh MODEL_ID` downloads only the configured model. `run.sh` invokes it only when observe-only mode is selected and the local weight file is missing. Benchmark assets are fetched from pinned upstream revisions by `benchmarks/compare_models.py` and are never stored in the source repository.

Upstream model licenses and immutable revisions are recorded in `ATTRIBUTION.md` and `benchmarks/model_catalog.json`. In particular, `sdmlai/cyber-jev` is CC-BY-NC-4.0: non-commercial use only. Do not treat its public download as permission for commercial deployment.

The Aegis default detector is allow-all. Model inference is opt-in and observe-only; the benchmark did not identify a safe blocking model. No raw request dataset or secrets are included in results.
