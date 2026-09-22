"""One bounded wait per pipeline stage. Each returns what the next stage needs."""
from __future__ import annotations

import json
from dataclasses import dataclass

from clients import ActiveMQ, Postgres, Redis, S3, wait_until
from seed import Ids
from settings import Settings


@dataclass(frozen=True)
class ConversionResult:
    outputdocumentmasterid: int
    pdf_url: str


@dataclass(frozen=True)
class DedupeResult:
    documentid: int
    rank1hash: str
    compressionjobid: int


@dataclass(frozen=True)
class CompressionResult:
    status: str
    compressedfilepath: str | None


def _job_versions(pg: Postgres, table: str, idcol: str, jobid: int) -> list[tuple[int, str, str | None]]:
    return pg.all(
        f'SELECT version, status, message FROM "{table}" WHERE {idcol} = %s ORDER BY version',
        (jobid,),
    )


def _fail_if_error(versions, label: str) -> None:
    for version, status, message in versions:
        if status == "error":
            raise AssertionError(f"{label} failed at version {version}: {message or 'no message'}")


def wait_for_conversion(pg: Postgres, s3: S3, redis: Redis, settings: Settings, ids: Ids) -> ConversionResult:
    def done():
        versions = _job_versions(pg, "FileConversionJob", "fileconversionjobid", ids.jobid)
        _fail_if_error(versions, "conversion")
        return any(v == 3 and s == "completed" for v, s, _ in versions)

    wait_until(done, settings.stage_timeout,
               describe=lambda: f"FileConversionJob versions={_job_versions(pg, 'FileConversionJob', 'fileconversionjobid', ids.jobid)}")

    (outputid,) = pg.one(
        'SELECT outputdocumentmasterid FROM "FileConversionJob" WHERE fileconversionjobid = %s AND version = 3',
        (ids.jobid,),
    )
    (pdf_url, parentid) = pg.one(
        'SELECT filepath, processingparentid FROM "DocumentMaster" WHERE documentmasterid = %s', (outputid,)
    )
    assert parentid == ids.documentmasterid
    assert pdf_url.lower().endswith(".pdf")
    key = pdf_url.split(f"/{settings.s3_bucket}/", 1)[1]
    pdf = s3.get(key)
    assert pdf[:5] == b"%PDF-", "converted object is not a PDF"

    def dedupe_message():
        for _, fields in redis.entries(settings.dedupe_stream):
            if fields.get("documentmasterid") == str(ids.documentmasterid):
                return fields
        return None

    fields = wait_until(dedupe_message, settings.stage_timeout,
                        describe=lambda: f"no dedupe message for documentmasterid={ids.documentmasterid}")
    assert fields["s3filepath"] == pdf_url
    assert fields["outputdocumentmasterid"] == str(outputid)
    return ConversionResult(outputdocumentmasterid=outputid, pdf_url=pdf_url)


def wait_for_attachment_conversions(pg: Postgres, settings: Settings, ids: Ids, expected: int) -> list[tuple[int, str]]:
    """Attachments File Conversion extracted from the upload: one DocumentMaster
    row each under `parentid`, re-queued as their own FileConversionJob.
    Returns (documentmasterid, filepath) per attachment once all have converted."""
    rows = pg.all(
        '''SELECT m.documentmasterid, m.filepath, j.fileconversionjobid
           FROM "DocumentMaster" m
           JOIN "FileConversionJob" j ON j.inputdocumentmasterid = m.documentmasterid AND j.version = 1
           WHERE m.parentid = %s ORDER BY m.documentmasterid''',
        (ids.documentmasterid,),
    )
    assert len(rows) == expected, f"expected {expected} attachment rows under parentid={ids.documentmasterid}, got {len(rows)}"

    def done():
        pending = []
        for masterid, filepath, jobid in rows:
            versions = _job_versions(pg, "FileConversionJob", "fileconversionjobid", jobid)
            _fail_if_error(versions, f"attachment conversion {filepath}")
            if not any(v == 3 and s == "completed" for v, s, _ in versions):
                pending.append(jobid)
        return not pending or None

    wait_until(done, settings.stage_timeout,
               describe=lambda: f"attachment FileConversionJobs still pending: {[j for _, _, j in rows if not any(v == 3 and s == 'completed' for v, s, _ in _job_versions(pg, 'FileConversionJob', 'fileconversionjobid', j))]}")
    return [(masterid, filepath) for masterid, filepath, _ in rows]


def wait_for_dedupe(
    pg: Postgres, redis: Redis, settings: Settings, ids: Ids,
    jobid: int | None = None, documentmasterid: int | None = None,
) -> DedupeResult:
    """`documentmasterid` is the id Dedupe records on `Documents`: the upload's
    own id for a PDF, or the converted output's id after File Conversion."""
    dedupe_jobid = jobid if jobid is not None else ids.jobid
    documents_masterid = documentmasterid if documentmasterid is not None else ids.documentmasterid

    def done():
        versions = _job_versions(pg, "DeduplicationJob", "deduplicationjobid", dedupe_jobid)
        _fail_if_error(versions, "dedupe")
        return any(v == 3 and s == "completed" for v, s, _ in versions)

    wait_until(done, settings.stage_timeout,
               describe=lambda: f"DeduplicationJob versions={_job_versions(pg, 'DeduplicationJob', 'deduplicationjobid', dedupe_jobid)}")

    row = wait_until(
        lambda: pg.one(
            '''SELECT d.documentid, h.rank1hash FROM "Documents" d
               JOIN "DocumentHashCodes" h ON h.documentid = d.documentid
               WHERE d.foiministryrequestid = %s AND d.documentmasterid = %s
               ORDER BY d.documentid DESC LIMIT 1''',
            (ids.ministryrequestid, documents_masterid),
        ),
        settings.stage_timeout,
        describe=lambda: f"no Documents/DocumentHashCodes row for documentmasterid={documents_masterid}",
    )
    documentid, rank1hash = row

    def compression_message():
        for _, fields in redis.entries(settings.compression_stream):
            if fields.get("documentmasterid") == str(ids.documentmasterid) or (
                "payload" in fields and json.loads(fields["payload"])["payload"]["documentmasterid"] == ids.documentmasterid
            ):
                return fields
        return None

    fields = wait_until(compression_message, settings.stage_timeout,
                        describe=lambda: f"no compression message for documentmasterid={ids.documentmasterid}")
    compressionjobid = int(fields["jobid"]) if "jobid" in fields else int(json.loads(fields["payload"])["payload"]["jobid"])

    def pagecount_message():
        return any(
            f.get("ministryrequestid") == str(ids.ministryrequestid)
            for _, f in redis.entries(settings.pagecount_stream)
        )

    wait_until(pagecount_message, settings.stage_timeout,
               describe=lambda: f"no pagecount message for ministryrequestid={ids.ministryrequestid}")
    return DedupeResult(documentid=documentid, rank1hash=rank1hash, compressionjobid=compressionjobid)


def wait_for_compression(pg: Postgres, s3: S3, settings: Settings, ids: Ids, compressionjobid: int) -> CompressionResult:
    def done():
        versions = _job_versions(pg, "CompressionJob", "compressionjobid", compressionjobid)
        _fail_if_error(versions, "compression")
        for v, s, _ in versions:
            if v == 3 and s in ("completed", "skipped"):
                return s
        return None

    status = wait_until(done, settings.stage_timeout,
                        describe=lambda: f"CompressionJob versions={_job_versions(pg, 'CompressionJob', 'compressionjobid', compressionjobid)}")
    (compressedfilepath,) = pg.one(
        'SELECT compressedfilepath FROM "DocumentMaster" WHERE documentmasterid = %s', (ids.documentmasterid,)
    )
    if status == "completed":
        assert compressedfilepath, "completed compression did not record compressedfilepath"
        key = compressedfilepath.split(f"/{settings.s3_bucket}/", 1)[1]
        assert s3.exists(key), f"compressed object missing: {key}"
    return CompressionResult(status=status, compressedfilepath=compressedfilepath)


def wait_for_ocr_dispatch(pg: Postgres, redis: Redis, activemq: ActiveMQ, settings: Settings, ids: Ids, compressionjobid: int) -> dict:
    def ocr_event():
        for _, fields in redis.entries(settings.ocr_stream):
            envelope = json.loads(fields["payload"])
            if envelope.get("event_type") == "document.ocr.requested" and envelope["payload"]["documentmasterid"] == ids.documentmasterid:
                return envelope
        return None

    wait_until(ocr_event, settings.stage_timeout,
               describe=lambda: f"no document.ocr.requested on {settings.ocr_stream} for documentmasterid={ids.documentmasterid}")

    def ocr_job_terminal():
        versions = _job_versions(pg, "OCRActiveMQJob", "ocractivemqjobid", compressionjobid)
        _fail_if_error(versions, "ocr dispatch")
        return any(v == 3 and s == "completed" for v, s, _ in versions)

    wait_until(ocr_job_terminal, settings.stage_timeout,
               describe=lambda: f"OCRActiveMQJob versions={_job_versions(pg, 'OCRActiveMQJob', 'ocractivemqjobid', compressionjobid)}")

    def queued_payload():
        message = activemq.consume_one()
        if message and message.get("documentmasterid") == ids.documentmasterid:
            return message
        return None

    payload = wait_until(queued_payload, settings.stage_timeout,
                         describe=lambda: f"no ActiveMQ message for documentmasterid={ids.documentmasterid}")
    assert payload["ministryrequestid"] == ids.ministryrequestid
    assert payload["bcgovcode"] == settings.bcgovcode
    assert payload.get("s3filepath") or payload.get("compresseds3filepath"), "OCR payload has no S3 path"
    return payload
