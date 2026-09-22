"""Rows reviewer_api/OCRServices create before the OCR worker sees a message."""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass

from clients import Postgres


@dataclass(frozen=True)
class Ids:
    ministryrequestid: int
    documentmasterid: int
    documentid: int
    requestnumber: str


def new_ids(prefix: int, n: int = 0) -> Ids:
    """Unique ids per test run; prefix separates tests, n separates documents in a batch."""
    seq = int(time.time()) % 100000
    base = prefix * 1_000_000 + seq * 10 + n
    return Ids(
        ministryrequestid=prefix * 1_000_000 + seq,   # one request per test
        documentmasterid=base,
        documentid=base,
        requestnumber=f"FOI-OCR-{prefix}-{seq}",
    )


def unique_pdf(sample_path: str, tag: str) -> bytes:
    """The sample PDF plus a trailing comment so every document has a distinct sha1.

    The mock returns the submitted bytes as the OCR result, so a test can prove the
    object in S3 came from *this* document."""
    with open(sample_path, "rb") as handle:
        return handle.read() + f"\n% e2e-ocr {tag}\n".encode()


def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def seed_document(pg: Postgres, ids: Ids, s3url: str, filename: str, filesize: int) -> None:
    pg.execute(
        '''INSERT INTO "DocumentMaster" (documentmasterid, filepath, ministryrequestid, isredactionready, createdby)
           VALUES (%s, %s, %s, false, 'e2e-ocr')''',
        (ids.documentmasterid, s3url, ids.ministryrequestid),
    )
    pg.execute(
        '''INSERT INTO "DocumentAttributes" (version, documentmasterid, attributes, createdby, isactive)
           VALUES (1, %s, %s, '{"user":"e2e-ocr"}', true)''',
        (ids.documentmasterid, json.dumps({"filesize": filesize, "extension": ".pdf", "incompatible": False})),
    )
    # statusid=1 and created_at=now() mirror DedupeServices' dedupedbservice.save_document_details.
    pg.execute(
        '''INSERT INTO "Documents" (documentid, version, filename, documentmasterid, foiministryrequestid, createdby, created_at, statusid)
           VALUES (%s, 1, %s, %s, %s, '{"user":"e2e-ocr"}', NOW(), 1)''',
        (ids.documentid, filename, ids.documentmasterid, ids.ministryrequestid),
    )


def queue_message(ids: Ids, s3url: str, compressed_s3url: str = "") -> dict:
    """The JSON OCRServices' models.OCRAzureMessage publishes; the worker's QueueMessage
    struct uses different casing (`documentId`, `S3FilePath`) and relies on Go's
    case-insensitive JSON field matching, so send the producer's form."""
    message = {
        "bcgovcode": "CITZ",
        "requestnumber": ids.requestnumber,
        "ministryrequestid": ids.ministryrequestid,
        "documentmasterid": ids.documentmasterid,
        "documentid": ids.documentid,
        "trigger": "recordupload",
        "s3filepath": s3url,
    }
    if compressed_s3url:
        message["compresseds3filepath"] = compressed_s3url
    return message
