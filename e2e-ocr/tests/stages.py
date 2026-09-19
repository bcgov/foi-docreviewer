"""Bounded waits on what the worker leaves behind: DocumentOCRJob rows, DocumentMaster, S3, mock stats."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass

from clients import MockAzure, Postgres, wait_until
from seed import Ids
from settings import Settings


@dataclass(frozen=True)
class OcrOutcome:
    ocrfilepath: str
    ocrfilesize: int | None
    chain: list[str]


def status_chain(pg: Postgres, ids: Ids) -> list[str]:
    rows = pg.all(
        'SELECT status FROM "DocumentOCRJob" WHERE documentid = %s AND ministryrequestid = %s ORDER BY version',
        (ids.documentid, ids.ministryrequestid),
    )
    return [row[0] for row in rows]


def _master(pg: Postgres, ids: Ids) -> tuple[str | None, bool]:
    row = pg.one('SELECT ocrfilepath, isredactionready FROM "DocumentMaster" WHERE documentmasterid = %s',
                 (ids.documentmasterid,))
    return (row[0], bool(row[1])) if row else (None, False)


def _ocrfilesize(pg: Postgres, ids: Ids) -> int | None:
    row = pg.one(
        '''SELECT (attributes::jsonb ->> 'ocrfilesize')::int FROM "DocumentAttributes"
           WHERE documentmasterid = %s AND isactive = true''',
        (ids.documentmasterid,),
    )
    return row[0] if row else None


def wait_for_ocr_done(pg: Postgres, settings: Settings, ids: Ids) -> OcrOutcome:
    """Done == azuredococrapi processed `ocrfileuploadsuccess`, which sets DocumentMaster.ocrfilepath
    (it writes no DocumentOCRJob row for that status)."""
    def done():
        chain = status_chain(pg, ids)
        if "ocrjobfailed" in chain:
            raise AssertionError(f"document {ids.documentid} failed: chain={chain}")
        path, ready = _master(pg, ids)
        return path if (path and ready) else None

    path = wait_until(done, settings.stage_timeout,
                      describe=lambda: f"chain={status_chain(pg, ids)} master={_master(pg, ids)}")
    return OcrOutcome(ocrfilepath=path, ocrfilesize=_ocrfilesize(pg, ids), chain=status_chain(pg, ids))


def wait_for_status(pg: Postgres, settings: Settings, ids: Ids, status: str) -> list[str]:
    chain = wait_until(lambda: (c := status_chain(pg, ids)) if status in c else None, settings.stage_timeout,
                       describe=lambda: f"chain={status_chain(pg, ids)}")
    return chain


def ocr_key_for(key: str) -> str:
    """Mirror s3services.GeneratePresignedUploadURL: '<name>OCR<ext>'."""
    name, ext = os.path.splitext(key)
    return f"{name}OCR{ext}"


def wait_for_mock_idle(mock: MockAzure, settings: Settings, quiet_seconds: float = 2.0) -> dict:
    """Return /_stats once its counters have not changed for quiet_seconds."""
    deadline = time.monotonic() + settings.stage_timeout
    last = mock.stats()
    last_change = time.monotonic()
    while time.monotonic() < deadline:
        time.sleep(0.5)
        now = mock.stats()
        if (now["analyze"], now["poll"], now["pdf"]) != (last["analyze"], last["poll"], last["pdf"]):
            last, last_change = now, time.monotonic()
        elif time.monotonic() - last_change >= quiet_seconds:
            return now
    raise AssertionError(f"mock never went idle; last stats={last}")


def op_for_sha1(stats: dict, digest: str) -> dict | None:
    return next((op for op in stats["ops"].values() if op["sha1"] == digest), None)
