"""Rows request-management-api / reviewer_api create before publishing work."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass

from clients import Postgres


@dataclass(frozen=True)
class Ids:
    ministryrequestid: int
    documentmasterid: int
    jobid: int
    batch: str
    requestnumber: str


def new_ids(prefix: int) -> Ids:
    """Unique ids per test run; prefix separates tests inside one run."""
    seq = int(time.time()) % 100000
    base = prefix * 1_000_000 + seq
    return Ids(
        ministryrequestid=base,
        documentmasterid=base,
        jobid=base,
        batch=f"e2e-batch-{base}",
        requestnumber=f"FOI-E2E-{base}",
    )


def ensure_path_mapper(pg: Postgres, bucket: str) -> None:
    """Workers look up S3 keys by bucket; Dedupe/Compression require category 'Records'.

    The api migrations already seed a 'Records'/<bucket> row for every bcgov code
    (including citz-dev-e) with `attributes` left NULL, so the INSERT below is a
    no-op for our bucket and the follow-up UPDATE is what actually sets the dev S3
    credentials the workers read via `s3credentials.s3accesskey`/`s3secretkey`.
    """
    pg.execute(
        '''INSERT INTO "DocumentPathMapper" (category, bucket, attributes, isactive, createdby)
           SELECT 'Records', %s, '{"s3accesskey":"dev","s3secretkey":"dev"}', true, 'e2e'
           WHERE NOT EXISTS (SELECT 1 FROM "DocumentPathMapper" WHERE bucket = %s AND category = 'Records')''',
        (bucket, bucket),
    )
    pg.execute(
        '''UPDATE "DocumentPathMapper" SET attributes = '{"s3accesskey":"dev","s3secretkey":"dev"}'
           WHERE bucket = %s AND category = 'Records' AND (attributes IS NULL OR attributes = '')''',
        (bucket,),
    )


def _seed_document(pg: Postgres, ids: Ids, s3url: str, filename: str, filesize: int, extension: str) -> None:
    pg.execute(
        '''INSERT INTO "DocumentMaster" (documentmasterid, filepath, ministryrequestid, isredactionready, createdby)
           VALUES (%s, %s, %s, false, 'e2e')''',
        (ids.documentmasterid, s3url, ids.ministryrequestid),
    )
    pg.execute(
        '''INSERT INTO "DocumentAttributes" (version, documentmasterid, attributes, createdby, isactive)
           VALUES (1, %s, %s, '{"user":"e2e"}', true)''',
        (ids.documentmasterid, json.dumps({"filesize": filesize, "extension": extension, "incompatible": False})),
    )


def seed_pdf_upload(pg: Postgres, ids: Ids, s3url: str, filename: str, filesize: int) -> None:
    _seed_document(pg, ids, s3url, filename, filesize, ".pdf")
    pg.execute(
        '''INSERT INTO "DeduplicationJob"
           (deduplicationjobid, version, ministryrequestid, batch, type, trigger, documentmasterid, filename, status)
           VALUES (%s, 1, %s, %s, 'rank1', 'recordupload', %s, %s, 'pushedtostream')''',
        (ids.jobid, ids.ministryrequestid, ids.batch, ids.documentmasterid, filename),
    )


def seed_docx_upload(pg: Postgres, ids: Ids, s3url: str, filename: str, filesize: int) -> None:
    _seed_document(pg, ids, s3url, filename, filesize, ".docx")
    pg.execute(
        '''INSERT INTO "FileConversionJob"
           (fileconversionjobid, version, ministryrequestid, batch, trigger, inputdocumentmasterid, filename, status)
           VALUES (%s, 1, %s, %s, 'recordupload', %s, %s, 'pushedtostream')''',
        (ids.jobid, ids.ministryrequestid, ids.batch, ids.documentmasterid, filename),
    )


def upload_message(ids: Ids, s3url: str, filename: str, filesize: int, extension: str) -> dict[str, str]:
    """The flat field map request-management-api publishes to conversion or dedupe."""
    return {
        "s3filepath": s3url,
        "requestnumber": ids.requestnumber,
        "bcgovcode": "CITZ",
        "filename": filename,
        "ministryrequestid": str(ids.ministryrequestid),
        "attributes": json.dumps({"filesize": filesize, "extension": extension, "incompatible": False}),
        "batch": ids.batch,
        "jobid": str(ids.jobid),
        "documentmasterid": str(ids.documentmasterid),
        "trigger": "recordupload",
        "createdby": "e2e",
        "usertoken": "NON_SECRET_E2E_TOKEN",
        "incompatible": "false",
    }
