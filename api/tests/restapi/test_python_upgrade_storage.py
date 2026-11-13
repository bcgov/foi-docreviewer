"""Exercise Reviewer's signed URL implementation with synthetic account data."""

import json
import boto3
from botocore.config import Config
import pytest
import requests
from reviewer_api.resources.foiflowmasterdata import (
    documentservice,
    redactionservice,
)


@pytest.fixture
def storage_record(monkeypatch):
    monkeypatch.setattr(
        documentservice,
        "getdocument",
        lambda self, id: {"filepath": "https://storage/mapper/test.pdf"},
    )
    monkeypatch.setattr(
        redactionservice,
        "getdocumentmapper",
        lambda self, key: {
            "bucket": "records",
            "attributes": json.dumps(
                {"s3accesskey": "synthetic", "s3secretkey": "synthetic-secret"}
            ),
        },
    )


def test_generated_signed_url_downloads_exact_bytes(app, storage_record, identity):
    client = boto3.client(
        "s3",
        endpoint_url="http://storage:8334",
        aws_access_key_id="synthetic",
        aws_secret_access_key="synthetic-secret",
        region_name="us-east-1",
        config=Config(
            signature_version="s3v4",
            connect_timeout=3,
            read_timeout=3,
            retries={"max_attempts": 0},
        ),
    )
    client.create_bucket(Bucket="records")
    payload = b"%PDF-1.4 synthetic reviewer upgrade bytes\n"
    client.put_object(
        Bucket="records", Key="test.pdf", Body=payload, ContentType="application/pdf"
    )
    signed = app.test_client().get(
        "/api/foiflow/oss/presigned/910001",
        headers={"Authorization": "Bearer " + identity.token()},
    )
    assert signed.status_code == 200
    url = signed.get_json(silent=True) or signed.get_data(as_text=True)
    assert url.startswith("https://storage:8333/records/test.pdf?")
    from urllib.parse import urlsplit, parse_qs, urlencode, urlunsplit

    parsed = urlsplit(url)
    query = parse_qs(parsed.query)
    assert query["X-Amz-Algorithm"] == ["AWS4-HMAC-SHA256"]
    assert query["X-Amz-Credential"][0].startswith("synthetic/")
    assert query["X-Amz-Expires"] == ["3600"]
    assert query["X-Amz-SignedHeaders"] == ["host"]
    assert len(query["X-Amz-Signature"][0]) == 64

    response = requests.get(url, verify="/test-tls/storage.crt", timeout=5)
    response.raise_for_status()
    assert response.content == payload
    assert response.headers["Content-Type"] == "application/pdf"
    query["X-Amz-Signature"] = ["0" * 64]
    tampered = urlunsplit(parsed._replace(query=urlencode(query, doseq=True)))
    assert (
        requests.get(tampered, verify="/test-tls/storage.crt", timeout=5).status_code
        == 403
    )


def test_missing_document_preserves_error_response(app, monkeypatch, identity):
    monkeypatch.setattr(documentservice, "getdocument", lambda self, id: None)
    response = app.test_client().get(
        "/api/foiflow/oss/presigned/910001",
        headers={"Authorization": "Bearer " + identity.token()},
    )
    assert response.status_code == 404
    assert response.get_json() == {"message": "Document not found"}
