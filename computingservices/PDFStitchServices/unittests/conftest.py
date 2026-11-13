"""Synthetic offline fixtures; never inherit developer service endpoints."""
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
for name, value in {
    "REDIS_HOST": "127.0.0.1", "REDIS_PORT": "1", "REDIS_PASSWORD": "",
    "NOTIFICATION_REDIS_HOST": "127.0.0.1", "NOTIFICATION_REDIS_PORT": "1",
    "NOTIFICATION_REDIS_PASSWORD": "", "ZIPPER_REDIS_HOST": "127.0.0.1",
    "ZIPPER_REDIS_PORT": "1", "ZIPPER_REDIS_PASSWORD": "",
    "ZIPPER_STREAM_KEY": "offline-zipper", "DIVISION_PDF_STITCH_STREAM_KEY": "offline-input",
    "DIVISION_STITCH_FOLDER_PATH": "Stitched/divisionname", "NUMBERING_ENABLED": "False",
    "NOTIFICATION_ENABLED": "False", "NOTIFICATION_STREAM_KEY": "offline-notifications",
}.items():
    os.environ[name] = value


def pdf_bytes(*labels, rotation=0, widget=False, protected=False):
    with fitz.open() as doc:
        for i, label in enumerate(labels):
            page = doc.new_page(width=612, height=792)
            page.insert_text((60, 60), label, fontsize=20)
            page.set_rotation(rotation)
            if widget and i == 0:
                field = fitz.Widget()
                field.field_name = "synthetic-name"
                field.field_type = fitz.PDF_WIDGET_TYPE_TEXT
                field.field_value = "VISIBLE FORM VALUE"
                field.rect = fitz.Rect(60, 100, 400, 150)
                field.text_fontsize = 18
                page.add_widget(field)
        options = dict(encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="reader") if protected else {}
        return doc.tobytes(**options)


@pytest.fixture
def stitch(monkeypatch, tmp_path):
    from services import basestitchservice as base_module
    from services import pdfstichservice as module

    inputs, uploads = {}, {}

    def download(file, credentials):
        return inputs[file.s3uripath]

    def upload(filename, data, requestnumber, bcgovcode, credentials):
        uploads[filename] = bytes(data)
        return {"filename": filename, "documentpath": "https://synthetic.invalid/" + filename, "success": True}

    monkeypatch.setattr(base_module, "gets3documentbytearray", download)
    monkeypatch.setattr(base_module, "uploadbytes", upload)
    monkeypatch.setattr(module, "numbering_enabled", "False")

    def run(files, numbering=False):
        monkeypatch.setattr(module, "numbering_enabled", str(numbering))
        division = SimpleNamespace(divisionname="Alpha", divisionid=1, files=files)
        result = module.pdfstitchservice().pdfstitchbasedondivision("SYN-001", None, "SYN", "Harms", division)
        if uploads:
            data = next(iter(uploads.values()))
            (tmp_path / "stitched.pdf").write_bytes(data)
            artifact_dir = os.getenv("PDFSTITCH_ARTIFACT_DIR")
            if artifact_dir:
                Path(artifact_dir).mkdir(parents=True, exist_ok=True)
                Path(artifact_dir, os.getenv("PYTEST_CURRENT_TEST").split(" ")[0].split("::")[-1] + ".pdf").write_bytes(data)
        return result

    return SimpleNamespace(inputs=inputs, uploads=uploads, run=run)


def file(name, **kwargs):
    return SimpleNamespace(recordid=1, filename=name, s3uripath="https://synthetic.invalid/" + name,
                           lastmodified="2026-01-01T00:00:00", **kwargs)
