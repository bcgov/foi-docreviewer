"""Run in a fresh production-image process as app_user, without test packages."""
import importlib
import importlib.metadata
import json
import os
import platform
import sys
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

for module in ["fitz", "reportlab.pdfgen.canvas", "PIL.Image", "pypdf", "psycopg2", "walrus", "redis", "boto3", "wrapt"]:
    importlib.import_module(module)

import fitz
from PIL import Image
from commons import convertimagetopdf

assert os.getuid() != 0, "Production smoke must run as app_user"
font = Path("commons/fonts/BCSans-Bold.ttf")
assert font.read_bytes()[:4] == b"\x00\x01\x00\x00"
assert fitz.Font(fontfile=str(font)).glyph_count > 0
image = BytesIO()
Image.new("RGB", (80, 160), "red").save(image, format="PNG")
with fitz.open(stream=convertimagetopdf(image.getvalue()), filetype="pdf") as doc:
    assert len(doc) == 1 and len(doc[0].get_pixmap().samples) > 0
print(json.dumps({"python": platform.python_version(), "os": platform.freedesktop_os_release()["PRETTY_NAME"],
                  "packages": {name: importlib.metadata.version(name) for name in
                               ["PyMuPDF", "reportlab", "Pillow", "pypdf", "psycopg2", "redis", "walrus", "marshmallow", "wrapt"]}}, sort_keys=True))
