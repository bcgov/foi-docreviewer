import ast
import inspect
import json
import logging
import os
import sys
from types import ModuleType, SimpleNamespace

import pytest


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def module(name, **attributes):
    value = ModuleType(name)
    for attribute, content in attributes.items():
        setattr(value, attribute, content)
    return value


psycopg2 = sys.modules.setdefault("psycopg2", module("psycopg2", connect=lambda **kwargs: None))
psycopg2.sql = SimpleNamespace(SQL=lambda query: query)
psycopg2.DatabaseError = Exception
sys.modules.setdefault("pypdf", module("pypdf", PdfReader=object, PdfWriter=object))
sys.modules.setdefault("fitz", module("fitz", Rect=object))
sys.modules.setdefault("PyPDF2", module("PyPDF2"))
reportlab = sys.modules.setdefault("reportlab", module("reportlab"))
sys.modules.setdefault("reportlab.lib", module("reportlab.lib"))
sys.modules.setdefault("reportlab.lib.pagesizes", module("reportlab.lib.pagesizes", letter=object()))
sys.modules.setdefault("reportlab.pdfgen", module("reportlab.pdfgen"))
sys.modules.setdefault("reportlab.pdfgen.canvas", module("reportlab.pdfgen.canvas", Canvas=object))
sys.modules.setdefault("reportlab.pdfbase", module("reportlab.pdfbase"))
sys.modules.setdefault("reportlab.pdfbase.ttfonts", module("reportlab.pdfbase.ttfonts", TTFont=lambda *_args: object()))
sys.modules.setdefault("reportlab.pdfbase.pdfmetrics", module("reportlab.pdfbase.pdfmetrics", registerFont=lambda *_args: None))

from services import s3documentservice
from utils.loggingutils import configure_logging


def message():
    return SimpleNamespace(
        bcgovcode="BCGOV",
        s3filepath="s3://private-bucket/input.pdf",
        filename="input.txt",
        requestnumber="FOI-123",
        ministryrequestid=22,
        documentmasterid=7,
        batch="batch-1",
        jobid=11,
        trigger="recordupload",
        attributes='{"secret": "not logged"}',
        usertoken="do-not-log",
    )


def logged_events(capsys):
    return [json.loads(line) for line in capsys.readouterr().out.splitlines()]


def install_hash_collaborators(monkeypatch):
    monkeypatch.setattr(
        s3documentservice,
        "__getcredentialsbybcgovcode",
        lambda _code: SimpleNamespace(s3accesskey="secret-key", s3secretkey="secret-value"),
    )
    monkeypatch.setattr(s3documentservice, "AWSRequestsAuth", lambda **_kwargs: object())
    monkeypatch.setattr(
        s3documentservice.requests,
        "get",
        lambda *_args, **_kwargs: SimpleNamespace(content=b"document", iter_lines=lambda: [b"document"]),
    )


def test_hashing_logs_safe_success_event(capsys, monkeypatch):
    install_hash_collaborators(monkeypatch)
    configure_logging()

    digest, pagecount = s3documentservice.gets3documenthashcode(message())

    assert digest
    assert pagecount == 1
    event = logged_events(capsys)[-1]
    assert event["event"] == "document_hash_completed"
    assert event["operation"] == "hash_document"
    assert event["document_master_id"] == 7
    assert event["pagecount"] == 1
    assert "s3filepath" not in event
    assert "secret-key" not in json.dumps(event)
    assert "usertoken" not in event
    assert "attributes" not in event


def test_hashing_failure_logs_safe_event_and_reraises(capsys, caplog, monkeypatch):
    install_hash_collaborators(monkeypatch)
    monkeypatch.setattr(s3documentservice.requests, "get", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("download failed")))
    configure_logging()
    caplog.set_level(logging.INFO)

    with pytest.raises(RuntimeError, match="download failed"):
        s3documentservice.gets3documenthashcode(message())

    event = logged_events(capsys)[-1]
    assert event["event"] == "document_processing_failed"
    assert event["operation"] == "hash_document"
    assert event["stage"] == "hash_document"
    assert event["exception_type"] == "RuntimeError"
    assert caplog.records[-1].exc_info[0] is RuntimeError
    assert "s3filepath" not in event
    assert "secret-value" not in json.dumps(event)
    assert "attributes" not in event
    assert "usertoken" not in event


def test_metadata_annotation_handling_emits_only_safe_json_stdout(capsys, monkeypatch):
    class MetadataReader:
        metadata = {"unsafe": "document metadata"}
        pages = [object()]

    class Writer:
        def write(self, buffer):
            buffer.write(b"flattened")

    class Client:
        def copy_object(self, **_kwargs):
            return None

    configure_logging()
    monkeypatch.setattr(
        s3documentservice,
        "PyPDF2",
        SimpleNamespace(PdfReader=lambda _source: MetadataReader(), PdfWriter=Writer),
    )
    monkeypatch.setattr(s3documentservice, "has_annotations", lambda _reader: False)
    monkeypatch.setattr(
        s3documentservice,
        "createpagesforcomments",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("annotation text must not be logged")),
    )
    monkeypatch.setattr(s3documentservice.boto3, "client", lambda *_args, **_kwargs: Client())
    monkeypatch.setattr(
        s3documentservice.requests,
        "put",
        lambda *_args, **_kwargs: SimpleNamespace(raise_for_status=lambda: None),
    )

    s3documentservice._clearmetadata(
        SimpleNamespace(content=b"document"),
        1,
        SimpleNamespace(pages=[object()]),
        "access-key",
        "secret-key",
        "s3://private-bucket/input.pdf",
        object(),
        "input.pdf",
    )

    output = capsys.readouterr().out.splitlines()
    events = [json.loads(line) for line in output]
    assert events[-1]["event"] == "document_processing_failed"
    assert events[-1]["stage"] == "metadata_annotation_handling"
    assert "annotation text" not in json.dumps(events)
    assert "private-bucket" not in json.dumps(events)
    assert "secret-key" not in json.dumps(events)


def test_metadata_flattening_annotation_failure_emits_only_safe_json_stdout(capsys, monkeypatch):
    class Annotation:
        rect = SimpleNamespace(
            is_valid=True,
            is_empty=False,
            is_infinite=False,
            width=10,
            height=10,
        )
        next = None

        @property
        def type(self):
            raise RuntimeError("annotation text must not be logged")

    class Page:
        rotation = 0
        rect = SimpleNamespace(width=100, height=200)
        first_annot = Annotation()
        first_widget = object()

        def get_pixmap(self, **_kwargs):
            return object()

    class SourceDocument:
        def __len__(self):
            return 1

        def load_page(self, _page_num):
            return Page()

    class OutputPage:
        def show_pdf_page(self, *_args):
            return None

        def set_rotation(self, _rotation):
            return None

        def insert_image(self, *_args, **_kwargs):
            return None

    class OutputDocument:
        def new_page(self, **_kwargs):
            return OutputPage()

        def save(self, buffer, **_kwargs):
            buffer.write(b"flattened")

    source_document = SourceDocument()
    output_document = OutputDocument()
    configure_logging()
    monkeypatch.setattr(
        s3documentservice,
        "fitz",
        SimpleNamespace(
            open=lambda *args, **kwargs: source_document if args or kwargs else output_document,
            Rect=lambda *args: args,
        ),
    )

    s3documentservice.__flattenfitz(b"document content")

    output = capsys.readouterr().out.splitlines()
    assert output
    events = [json.loads(line) for line in output]
    assert events[-1]["event"] == "document_processing_failed"
    assert events[-1]["stage"] == "flatten_annotation"
    assert "annotation text" not in json.dumps(events)


def test_metadata_cleanup_helpers_have_no_active_print_calls():
    helper_names = (
        "split_comments_to_pages",
        "wrap_text",
        "_clearmetadata",
        "__flattenfitz",
        "__rendercommentsonnewpage",
        "createpagesforcomments",
    )
    for name in helper_names:
        source = inspect.getsource(getattr(s3documentservice, name))
        calls = [
            node
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print"
        ]
        assert calls == [], name
