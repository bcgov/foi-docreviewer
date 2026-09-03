"""Unit tests for core.s3 -- boto3 is faked with moto, no real AWS."""

import boto3
import pytest
from moto import mock_aws

from core import s3 as s3_mod
from core.s3 import S3Error, fetch_pdf, parse_s3_uri, suffix_uri, upload_pdf
from tests.pdf_helpers import pdf_bytes


@pytest.fixture(autouse=True)
def _aws_env(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    # moto intercepts the default AWS endpoint; make sure a dev's real
    # S3_ENDPOINT_URL does not leak in.
    monkeypatch.delenv("S3_ENDPOINT_URL", raising=False)
    monkeypatch.delenv("S3_FORCE_PATH_STYLE", raising=False)
    from config.settings import get_settings

    get_settings.cache_clear()
    s3_mod._client = None
    yield
    s3_mod._client = None
    get_settings.cache_clear()


@pytest.fixture
def s3():
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="src")
        client.create_bucket(Bucket="dst")
        yield client


def test_parse_s3_uri():
    assert parse_s3_uri("s3://b/a/b/c.pdf") == ("b", "a/b/c.pdf")
    with pytest.raises(S3Error):
        parse_s3_uri("https://example.com/a.pdf")
    with pytest.raises(S3Error):
        parse_s3_uri("s3://bucket-only")


def test_suffix_uri():
    assert (
        suffix_uri("s3://edu-test-e/EDU-2023-09261143/f295649a.pdf", "PREPROCESSED")
        == "s3://edu-test-e/EDU-2023-09261143/f295649aPREPROCESSED.pdf"
    )
    # dots in the prefix are left alone; only the filename stem is touched
    assert (
        suffix_uri("s3://b/dir.v2/name.pdf", "X") == "s3://b/dir.v2/nameX.pdf"
    )
    # no extension
    assert suffix_uri("s3://b/dir/name", "X") == "s3://b/dir/nameX"


def test_endpoint_url_and_path_style_are_applied(monkeypatch):
    """An S3-compatible store (BC Gov, MinIO) needs a custom endpoint + path style."""
    monkeypatch.setenv("S3_ENDPOINT_URL", "https://obj.example.gov.bc.ca")
    monkeypatch.setenv("S3_FORCE_PATH_STYLE", "true")
    from config.settings import get_settings

    get_settings.cache_clear()
    s3_mod._client = None

    client = s3_mod.get_s3_client()
    assert client.meta.endpoint_url == "https://obj.example.gov.bc.ca"
    assert client.meta.config.s3["addressing_style"] == "path"


def test_default_client_targets_aws(monkeypatch):
    from config.settings import get_settings

    get_settings.cache_clear()
    s3_mod._client = None
    client = s3_mod.get_s3_client()
    assert "amazonaws.com" in client.meta.endpoint_url


async def test_fetch_pdf_downloads_the_object(s3, tmp_path):
    body = pdf_bytes(clip=True)
    s3.put_object(Bucket="src", Key="in/a.pdf", Body=body)

    dst = tmp_path / "a.pdf"
    out = await fetch_pdf("s3://src/in/a.pdf", dst)

    assert out == dst
    assert dst.read_bytes() == body


async def test_fetch_pdf_missing_object_raises(s3, tmp_path):
    with pytest.raises(S3Error, match="head"):
        await fetch_pdf("s3://src/nope.pdf", tmp_path / "x.pdf")


async def test_fetch_pdf_rejects_a_non_pdf_body(s3, tmp_path):
    s3.put_object(Bucket="src", Key="in/x", Body=b"<html>not a pdf</html>")
    with pytest.raises(S3Error, match="not a PDF"):
        await fetch_pdf("s3://src/in/x", tmp_path / "x.pdf")


async def test_fetch_pdf_rejects_an_object_over_the_cap(s3, tmp_path, monkeypatch):
    from config.settings import get_settings

    monkeypatch.setenv("MAX_PDF_BYTES", "10")
    get_settings.cache_clear()
    s3.put_object(Bucket="src", Key="big.pdf", Body=b"%PDF-" + b"x" * 5000)

    with pytest.raises(S3Error, match="cap"):
        await fetch_pdf("s3://src/big.pdf", tmp_path / "x.pdf")


async def test_upload_pdf_puts_the_object(s3, tmp_path):
    src = tmp_path / "out.pdf"
    src.write_bytes(pdf_bytes(clip=False))

    uri = await upload_pdf(src, "s3://dst/preprocessed/job-1.pdf")

    assert uri == "s3://dst/preprocessed/job-1.pdf"
    got = s3.get_object(Bucket="dst", Key="preprocessed/job-1.pdf")
    assert got["Body"].read() == src.read_bytes()
    assert got["ContentType"] == "application/pdf"


async def test_upload_pdf_bad_bucket_raises(s3, tmp_path):
    src = tmp_path / "out.pdf"
    src.write_bytes(b"%PDF-x")
    with pytest.raises(S3Error, match="put"):
        await upload_pdf(src, "s3://no-such-bucket/x.pdf")
