import json
import threading
from flask import Flask, request, jsonify
import uvicorn
from fastapi import FastAPI, Request
counts = {"flask": 0, "fastapi": 0}
lock = threading.Lock()
def row(method, headers, path, query, body, service):
    with lock: counts[service] += 1
    return {"service": service, "method": method, "host": headers.get("host"), "path": path, "query": query, "body": body.decode("utf-8","replace")}
flask_app = Flask("aegis-lab-flask")
@flask_app.route("/", defaults={"path":""}, methods=["GET","POST","PUT","DELETE","HEAD"])
@flask_app.route("/<path:path>", methods=["GET","POST","PUT","DELETE","HEAD"])
def flask_route(path):
    if request.path == "/_counters": return jsonify(counts)
    return jsonify(row(request.method, request.headers, request.path, request.query_string.decode(), request.get_data(), "flask"))
fastapi_app = FastAPI()
@fastapi_app.api_route("/{path:path}", methods=["GET","POST","PUT","DELETE","HEAD"])
async def fastapi_route(path: str, req: Request):
    if req.url.path == "/_counters": return counts
    return row(req.method, req.headers, req.url.path, str(req.url.query), await req.body(), "fastapi")
def run_flask(): flask_app.run(host="0.0.0.0",port=5000,threaded=True,use_reloader=False)
def run_fastapi(): uvicorn.run(fastapi_app,host="0.0.0.0",port=8000,access_log=False)
threading.Thread(target=run_flask,daemon=True).start()
threading.Thread(target=run_fastapi,daemon=True).start()
threading.Event().wait()
