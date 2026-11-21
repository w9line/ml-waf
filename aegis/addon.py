import asyncio
import json
import os
import threading
import time
from pathlib import Path
from mitmproxy import http
import yaml
from aegis.detector import detector_from_config

class AegisAddon:
    def __init__(self):
        self.path = os.environ.get("AEGIS_TELEMETRY", "/run/aegis/telemetry.jsonl")
        config_path = Path(os.environ.get("AEGIS_CONFIG", "/etc/aegis/config.yaml"))
        try:
            with config_path.open(encoding="utf-8") as stream:
                config = yaml.safe_load(stream) or {}
        except FileNotFoundError:
            config = {}
        self.detector = detector_from_config(config.get("detector", {}))
        self.heartbeat = os.environ.get("AEGIS_HEARTBEAT", "/run/aegis/proxy.heartbeat")
        self._heartbeat_task = None
        self._telemetry_lock = threading.Lock()

    def running(self):
        self._heartbeat_task = asyncio.create_task(self._beat(), name="aegis-heartbeat")

    async def _beat(self):
        while True:
            try:
                with open(self.heartbeat, "w", encoding="utf-8") as stream:
                    stream.write(str(time.time()))
            except OSError:
                pass
            await asyncio.sleep(0.5)

    def done(self):
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
        close = getattr(self.detector, "close", None)
        if close is not None:
            close()

    def _record(self, metadata, result):
        row = {"ts": time.time(), **metadata, **result}
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with self._telemetry_lock:
                with open(self.path, "a", encoding="utf-8") as out:
                    out.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        except OSError:
            pass

    def request(self, flow: http.HTTPFlow):
        request = flow.request
        metadata = {"method": request.method, "host_header": request.headers.get("host", ""),
                    "path": request.path.split("?", 1)[0], "dst": flow.server_conn.address}
        submit = getattr(self.detector, "submit", None)
        if callable(submit):
            submit(request, lambda result: self._record(metadata, result))
            return
        start = time.perf_counter()
        result = self.detector.predict(request)
        result["latency_ms"] = (time.perf_counter() - start) * 1000.0
        self._record(metadata, result)

addons = [AegisAddon()]
