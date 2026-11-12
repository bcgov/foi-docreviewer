"""Run in a fresh production-image process, before pytest installs stubs."""

import importlib
import io
import os
import sys


def main():
    print(sys.version, flush=True)
    assert sys.version_info[:2] == (3, 13)
    assert os.getuid() != 0, "Run runtime checks as the configured application user"
    for name in ("psycopg2", "fitz", "reportlab", "redis", "boto3", "wrapt",
                 "pypdf", "PyPDF2", "marshmallow"):
        module = importlib.import_module(name)
        print(f"Imported {name}: {module.__file__}", flush=True)

    from redis import Redis
    from walrus import Database

    assert isinstance(Database(), Redis)

    # Exercise native PDF operations as well as module loading.
    import fitz
    import PyPDF2
    from pypdf import PdfReader
    from reportlab.pdfgen.canvas import Canvas

    output = io.BytesIO()
    canvas = Canvas(output, invariant=True)
    for text in ("Synthetic runtime check", "Second page"):
        canvas.drawString(72, 720, text)
        canvas.showPage()
    canvas.save()
    data = output.getvalue()
    assert len(PdfReader(io.BytesIO(data)).pages) == 2
    assert len(PyPDF2.PdfReader(io.BytesIO(data)).pages) == 2
    with fitz.open(stream=data, filetype="pdf") as document:
        assert len(document) == 2
        assert "Synthetic runtime check" in document[0].get_text()
        assert document[0].get_pixmap().width > 0
    print("Native imports, PDF generation, reading and rendering passed")


if __name__ == "__main__":
    main()
