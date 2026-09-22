"""Mock of Azure Document Intelligence (prebuilt-read, output=pdf) for the OCR harness.

Only the three routes the worker calls are implemented, plus /_control and /_stats
for tests. All state lives in `state`; every handler takes `state.lock`.
"""
from __future__ import annotations

import base64
import hashlib
import os
import threading
import time
import uuid

import requests
from flask import Flask, Response, jsonify, request

app = Flask(__name__)

API_VERSION = "2024-11-30"
RESULTS_PATH = "/documentintelligence/documentModels/prebuilt-read/analyzeResults"

DEFAULT_SCENARIO = {
    "processing_polls": 2,
    "submit_429_first": 0,
    "poll_429_first": 0,
    "result_429_first": 0,
    "retry_after_seconds": 2,
    "max_concurrent_analyze": None,
    "fail_ops_matching": [],
    "submit_latency_ms": 0,
}

MINIMAL_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF\n"
)


class State:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.reset()

    def reset(self, scenario: dict | None = None) -> None:
        self.scenario = {**DEFAULT_SCENARIO, **(scenario or {})}
        self.ops: dict[str, dict] = {}
        self.counts = {"analyze": 0, "poll": 0, "pdf": 0}
        self.http429 = {"submit": 0, "poll": 0, "pdf": 0}
        self.in_flight = 0
        self.max_concurrent = 0
        self.analyze_timestamps: list[float] = []

    def snapshot(self) -> dict:
        return {
            **self.counts,
            "http429": dict(self.http429),
            "max_concurrent_analyze": self.max_concurrent,
            "analyze_timestamps": list(self.analyze_timestamps),
            "ops": {
                op_id: {k: v for k, v in op.items() if k != "bytes"} for op_id, op in self.ops.items()
            },
        }


state = State()


def azure_error(status: int, code: str, message: str, retry_after: int | None = None) -> Response:
    resp = jsonify({"error": {"code": code, "message": message}})
    resp.status_code = status
    if retry_after is not None:
        resp.headers["Retry-After"] = str(retry_after)
    return resp


def throttle(kind: str, counter_key: str) -> Response | None:
    """Serve a 429 while the scenario's `<kind>_429_first` budget is not used up.

    Caller holds state.lock."""
    remaining = state.scenario[f"{kind}_429_first"] - state.http429[counter_key]
    if remaining > 0:
        state.http429[counter_key] += 1
        return azure_error(429, "429", "Requests to the Analyze operation have exceeded call rate limit",
                           retry_after=state.scenario["retry_after_seconds"])
    return None


def base_url() -> str:
    return os.environ.get("MOCK_AZURE_BASE_URL") or request.host_url.rstrip("/")


def load_source(body: dict) -> tuple[bytes, str]:
    """Return (pdf bytes, key). key is the URL path for urlSource, '' for base64Source."""
    if "base64Source" in body:
        return base64.b64decode(body["base64Source"]), ""
    if "urlSource" in body:
        url = body["urlSource"]
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.content, url.split("?", 1)[0]
    raise ValueError("body must contain base64Source or urlSource")


@app.get("/healthz")
def healthz():
    return "ok", 200


@app.post("/documentintelligence/documentModels/prebuilt-read:analyze")
def analyze():
    with state.lock:
        state.counts["analyze"] += 1
        state.analyze_timestamps.append(time.time())
        state.in_flight += 1
        state.max_concurrent = max(state.max_concurrent, state.in_flight)
        cap = state.scenario["max_concurrent_analyze"]
        over_cap = cap is not None and state.in_flight > cap
        throttled = throttle("submit", "submit")
        latency = state.scenario["submit_latency_ms"] / 1000
    try:
        if latency:
            time.sleep(latency)
        if over_cap:
            with state.lock:
                state.http429["submit"] += 1
            return azure_error(429, "429", "concurrent analyze cap exceeded",
                               retry_after=state.scenario["retry_after_seconds"])
        if throttled is not None:
            return throttled
        body = request.get_json(silent=True) or {}
        try:
            data, key = load_source(body)
        except (ValueError, requests.RequestException) as error:
            return azure_error(400, "InvalidRequest", str(error))
        if not data.startswith(b"%PDF"):
            return azure_error(400, "InvalidContent", "source is not a PDF")
        op_id = uuid.uuid4().hex
        with state.lock:
            state.ops[op_id] = {
                "key": key,
                "sha1": hashlib.sha1(data).hexdigest(),
                "polls": 0,
                "status": "notStarted",
                "pdf_fetched": False,
                "apim_request_id": str(uuid.uuid4()),
                "bytes": data,
            }
            apim = state.ops[op_id]["apim_request_id"]
        resp = Response(status=202)
        resp.headers["Operation-Location"] = f"{base_url()}{RESULTS_PATH}/{op_id}?api-version={API_VERSION}"
        resp.headers["Apim-Request-Id"] = apim
        return resp
    finally:
        with state.lock:
            state.in_flight -= 1


def _matches_failure(op: dict) -> bool:
    needles = state.scenario["fail_ops_matching"]
    return any(n and (n in op["key"] or n in op["sha1"]) for n in needles)


@app.get(f"{RESULTS_PATH}/<op_id>")
def poll(op_id: str):
    with state.lock:
        state.counts["poll"] += 1
        throttled = throttle("poll", "poll")
        if throttled is not None:
            return throttled
        op = state.ops.get(op_id)
        if op is None:
            return azure_error(404, "NotFound", f"operation {op_id} not found")
        op["polls"] += 1
        if op["polls"] == 1:
            op["status"] = "notStarted"
        elif op["polls"] <= state.scenario["processing_polls"] + 1:
            op["status"] = "running"
        elif _matches_failure(op):
            op["status"] = "failed"
        else:
            op["status"] = "succeeded"
        status = op["status"]
    payload: dict = {
        "status": status,
        "createdDateTime": "2026-01-01T00:00:00Z",
        "lastUpdatedDateTime": "2026-01-01T00:00:00Z",
    }
    if status == "succeeded":
        payload["analyzeResult"] = {
            "apiVersion": API_VERSION,
            "modelId": "prebuilt-read",
            "content": "e2e",
            "pages": [{"pageNumber": 1, "lines": [{"content": "e2e"}]}],
        }
    elif status == "failed":
        payload["error"] = {"code": "InvalidRequest", "message": "e2e forced failure"}
    return jsonify(payload)


@app.get(f"{RESULTS_PATH}/<op_id>/pdf")
def pdf(op_id: str):
    with state.lock:
        state.counts["pdf"] += 1
        throttled = throttle("result", "pdf")
        if throttled is not None:
            return throttled
        op = state.ops.get(op_id)
        if op is None:
            return azure_error(404, "NotFound", f"operation {op_id} not found")
        if op["status"] != "succeeded":
            return azure_error(409, "Conflict", f"operation status is {op['status']}")
        op["pdf_fetched"] = True
        data = op["bytes"] or MINIMAL_PDF
    return Response(data, status=200, content_type="application/pdf")


@app.post("/_control")
def set_control():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "JSON object expected"}), 400
    unknown = sorted(set(body) - set(DEFAULT_SCENARIO))
    if unknown:
        return jsonify({"error": f"unknown scenario keys: {unknown}"}), 400
    with state.lock:
        state.reset(body)
        scenario = dict(state.scenario)
    return jsonify(scenario)


@app.delete("/_control")
def reset_control():
    with state.lock:
        state.reset()
        scenario = dict(state.scenario)
    return jsonify(scenario)


@app.get("/_stats")
def stats():
    with state.lock:
        return jsonify(state.snapshot())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), threaded=True)
