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
