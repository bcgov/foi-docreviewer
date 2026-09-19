from __future__ import annotations

import base64
import json

import pytest

import app as mock

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
ANALYZE = "/documentintelligence/documentModels/prebuilt-read:analyze?_overload=analyzeDocument&api-version=2024-11-30&output=pdf"


@pytest.fixture()
def client():
    mock.state.reset()
    mock.app.config["TESTING"] = True
    return mock.app.test_client()


def submit(client, data: bytes = PDF):
    return client.post(ANALYZE, json={"base64Source": base64.b64encode(data).decode()})


def test_analyze_returns_202_with_operation_headers(client):
    resp = submit(client)
    assert resp.status_code == 202
    loc = resp.headers["Operation-Location"]
    assert "/documentintelligence/documentModels/prebuilt-read/analyzeResults/" in loc
    assert loc.endswith("?api-version=2024-11-30")
    assert resp.headers["Apim-Request-Id"]


def test_analyze_rejects_non_pdf_base64(client):
    resp = submit(client, b"hello")
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "InvalidContent"


def test_poll_progresses_notstarted_running_succeeded(client):
    loc = submit(client).headers["Operation-Location"]
    path = loc.split("http://localhost", 1)[-1]
    statuses = [client.get(path).get_json()["status"] for _ in range(4)]
    assert statuses == ["notStarted", "running", "running", "succeeded"]
    assert client.get(path).get_json()["analyzeResult"]["pages"][0]["pageNumber"] == 1


def test_pdf_available_only_after_succeeded(client):
    loc = submit(client).headers["Operation-Location"]
    path = loc.split("http://localhost", 1)[-1].split("?", 1)[0]
    assert client.get(path + "/pdf?api-version=2024-11-30").status_code == 409
    for _ in range(4):
        client.get(path + "?api-version=2024-11-30")
    resp = client.get(path + "/pdf?api-version=2024-11-30")
    assert resp.status_code == 200
    assert resp.headers["Content-Type"] == "application/pdf"
    assert resp.data == PDF


def test_unknown_operation_is_404_with_envelope(client):
    resp = client.get("/documentintelligence/documentModels/prebuilt-read/analyzeResults/nope?api-version=2024-11-30")
    assert resp.status_code == 404
    assert resp.get_json()["error"]["code"] == "NotFound"


def test_stats_count_requests_and_ops(client):
    loc = submit(client).headers["Operation-Location"]
    path = loc.split("http://localhost", 1)[-1]
    client.get(path)
    stats = client.get("/_stats").get_json()
    assert stats["analyze"] == 1 and stats["poll"] == 1 and stats["pdf"] == 0
    assert stats["max_concurrent_analyze"] == 1
    (op,) = stats["ops"].values()
    assert op["polls"] == 1 and op["status"] == "notStarted" and op["pdf_fetched"] is False
    assert len(op["sha1"]) == 40


def test_healthz(client):
    assert client.get("/healthz").status_code == 200


def control(client, **scenario):
    resp = client.post("/_control", json=scenario)
    assert resp.status_code == 200, resp.data
    return resp.get_json()


def test_control_rejects_unknown_keys(client):
    resp = client.post("/_control", json={"nope": 1})
    assert resp.status_code == 400
    assert "nope" in resp.get_json()["error"]


def test_control_reset_restores_defaults_and_clears_stats(client):
    control(client, processing_polls=5)
    submit(client)
    assert client.delete("/_control").get_json()["processing_polls"] == 2
    assert client.get("/_stats").get_json()["analyze"] == 0


def test_submit_429_first_n_then_202(client):
    control(client, submit_429_first=2, retry_after_seconds=7)
    first, second, third = (submit(client) for _ in range(3))
    assert (first.status_code, second.status_code, third.status_code) == (429, 429, 202)
    assert first.headers["Retry-After"] == "7"
    assert first.get_json()["error"]["code"] == "429"
    assert client.get("/_stats").get_json()["http429"]["submit"] == 2


def test_poll_429_first_n_does_not_advance_operation(client):
    control(client, poll_429_first=1)
    loc = submit(client).headers["Operation-Location"]
    path = loc.split("http://localhost", 1)[-1]
    assert client.get(path).status_code == 429
    assert client.get(path).get_json()["status"] == "notStarted"


def test_result_429_first_n(client):
    control(client, result_429_first=1, processing_polls=0)
    loc = submit(client).headers["Operation-Location"]
    path = loc.split("http://localhost", 1)[-1].split("?", 1)[0]
    client.get(path + "?api-version=2024-11-30")
    client.get(path + "?api-version=2024-11-30")
    assert client.get(path + "/pdf?api-version=2024-11-30").status_code == 429
    assert client.get(path + "/pdf?api-version=2024-11-30").status_code == 200


def test_fail_ops_matching_by_sha1(client):
    import hashlib
    control(client, fail_ops_matching=[hashlib.sha1(PDF).hexdigest()[:12]], processing_polls=0)
    loc = submit(client).headers["Operation-Location"]
    path = loc.split("http://localhost", 1)[-1]
    client.get(path)
    body = client.get(path).get_json()
    assert body["status"] == "failed"
    assert body["error"]["code"] == "InvalidRequest"
    assert client.get(path.split("?", 1)[0] + "/pdf?api-version=2024-11-30").status_code == 409


def test_max_concurrent_analyze_serves_429_over_cap():
    """Two concurrent submits with cap=1 and latency: one 202, one 429."""
    import threading
    mock.state.reset({"max_concurrent_analyze": 1, "submit_latency_ms": 300})
    codes: list[int] = []

    def go():
        # one test client per thread: the Flask test client is not thread-safe
        codes.append(submit(mock.app.test_client()).status_code)

    threads = [threading.Thread(target=go) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(codes) == [202, 429]
    stats = mock.app.test_client().get("/_stats").get_json()
    assert stats["max_concurrent_analyze"] == 2
    assert stats["http429"]["submit"] == 1


def test_url_source_is_fetched(client, monkeypatch):
    class FakeResp:
        content = PDF
        def raise_for_status(self): pass
    monkeypatch.setattr(mock.requests, "get", lambda url, timeout: FakeResp())
    resp = client.post(ANALYZE, json={"urlSource": "http://seaweedfs:8333/citz-dev-e/requests/x/a.pdf?X-Amz=1"})
    assert resp.status_code == 202
    (op,) = client.get("/_stats").get_json()["ops"].values()
    assert op["key"] == "http://seaweedfs:8333/citz-dev-e/requests/x/a.pdf"
