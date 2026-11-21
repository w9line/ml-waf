from __future__ import annotations
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from threading import BoundedSemaphore
from typing import Any, Callable
import time

class Detector:
    def predict(self, request: Any) -> dict:
        raise NotImplementedError

class AllowAllDetector(Detector):
    def predict(self, request: Any) -> dict:
        return {"label": "benign", "score": 0.0, "latency_ms": 0.0, "mode": "allow-all"}

class ObserveOnlyDetector(Detector):
    """Model observer. Inference is queued off the proxy event loop and never blocks traffic."""
    def __init__(self, model: str, model_path: str, threshold: float = 0.5, max_pending: int = 128):
        from aegis.model_backends import ADAPTERS
        try:
            adapter_type = ADAPTERS[model]
        except KeyError as exc:
            raise ValueError(f"unsupported model adapter: {model}") from exc
        self.model = model
        self.threshold = float(threshold)
        self.backend = adapter_type(Path(model_path))
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="aegis-observe")
        self._slots = BoundedSemaphore(max(1, int(max_pending)))

    @staticmethod
    def _sample(request: Any) -> dict:
        if isinstance(request, dict) and "request" in request:
            return request
        method = str(getattr(request, "method", "GET"))
        target = str(getattr(request, "path", "/")) or "/"
        version = str(getattr(request, "http_version", "HTTP/1.1"))
        if not version.upper().startswith("HTTP/"):
            version = "HTTP/" + version
        headers = []
        source_headers = getattr(request, "headers", {})
        try:
            items = source_headers.items()
        except AttributeError:
            items = []
        for key, value in items:
            headers.append((str(key).title(), str(value)))
        raw_body = getattr(request, "raw_content", b"") or b""
        body = raw_body.decode("utf-8", "replace") if isinstance(raw_body, bytes) else str(raw_body)
        head = f"{method} {target} {version}\r\n" + "".join(f"{key}: {value}\r\n" for key, value in headers) + "\r\n"
        return {"request": head + body}

    def _predict_sample(self, sample: dict) -> dict:
        started = time.perf_counter()
        output = self.backend.predict(sample)
        score = float(output["score"])
        elapsed = (time.perf_counter() - started) * 1000.0
        return {"label": "malicious" if score >= self.threshold else "benign", "score": score,
                "latency_ms": float(output.get("latency_ms", elapsed)), "mode": "observe-only", "model": self.model}

    def predict(self, request: Any) -> dict:
        try:
            return self._predict_sample(self._sample(request))
        except Exception as exc:
            return {"label": "inference_error", "score": 0.0, "latency_ms": 0.0,
                    "mode": "observe-only", "model": self.model, "error_type": type(exc).__name__}

    def submit(self, request: Any, callback: Callable[[dict], None]) -> bool:
        try:
            sample = self._sample(request)
        except Exception as exc:
            callback({"label": "inference_error", "score": 0.0, "latency_ms": 0.0,
                     "mode": "observe-only", "model": self.model, "error_type": type(exc).__name__})
            return False
        if not self._slots.acquire(blocking=False):
            callback({"label": "not_scored_queue_full", "score": 0.0, "latency_ms": 0.0,
                     "mode": "observe-only", "model": self.model})
            return False
        try:
            future = self._executor.submit(self._predict_sample, sample)
        except Exception as exc:
            self._slots.release()
            callback({"label": "inference_error", "score": 0.0, "latency_ms": 0.0,
                     "mode": "observe-only", "model": self.model, "error_type": type(exc).__name__})
            return False
        def finished(done: Future) -> None:
            self._slots.release()
            try:
                result = done.result()
            except Exception as exc:
                result = {"label": "inference_error", "score": 0.0, "latency_ms": 0.0,
                          "mode": "observe-only", "model": self.model, "error_type": type(exc).__name__}
            try:
                callback(result)
            except Exception:
                pass
        future.add_done_callback(finished)
        return True

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

def detector_from_config(settings: dict | None = None) -> Detector:
    settings = settings or {}
    mode = str(settings.get("mode", "allow-all"))
    if mode == "allow-all":
        return AllowAllDetector()
    if mode == "observe-only":
        model = str(settings.get("model", ""))
        path = str(settings.get("model_path", ""))
        if not model or not path:
            raise ValueError("observe-only requires detector.model and detector.model_path")
        return ObserveOnlyDetector(model, path, float(settings.get("threshold", 0.5)), int(settings.get("max_pending", 128)))
    raise ValueError(f"unsupported detector mode: {mode}")
