from io import BytesIO
from types import SimpleNamespace

import fitz
import pytest
from PIL import Image

from unittests.conftest import file, pdf_bytes


@pytest.mark.parametrize("numbering", [False, True])
def test_merge_order_rotations_skips_and_attachment_contract(stitch, numbering):
    files = [file(n) for n in ["first.pdf", "broken.pdf", "secret.pdf", "last.pdf", "attachment.txt"]]
    files[3].rotatedpages = SimpleNamespace(**{"1": 90})
    stitch.inputs.update({files[0].s3uripath: pdf_bytes("FIRST", "SECOND"),
                          files[1].s3uripath: b"not a PDF", files[2].s3uripath: pdf_bytes("SECRET", protected=True),
                          files[3].s3uripath: pdf_bytes("THIRD")})
    result = stitch.run(files, numbering)
    assert result["stitchedoutput"] == {"divisionname": "Alpha", "stitchedfiles": ["first.pdf", "last.pdf"],
                                        "stichedfilecount": 2, "skippedfiles": ["broken.pdf", "secret.pdf"], "skippedfilecount": 2}
    assert [f["filename"] for f in result["filestozip"]] == ["Stitched/Alpha/SYN-001 - Stitched - Alpha.pdf", "Stitched/Alpha/attachment.txt"]
    assert result["filestozip"][1]["s3uripath"] == files[4].s3uripath
    with fitz.open(stream=next(iter(stitch.uploads.values())), filetype="pdf") as doc:
        assert len(doc) == 3
        assert [p.get_text().splitlines()[0] for p in doc] == ["FIRST", "SECOND", "THIRD"]
        assert [p.rotation for p in doc] == [0, 0, 90]
        # Existing numbering on rotated pages can fall outside their crop box.
        assert ("PAGE 1 OF 3" in doc[0].get_text()) is numbering
        assert ("PAGE 2 OF 3" in doc[1].get_text()) is numbering


@pytest.mark.parametrize("format,size", [("PNG", (200, 600)), ("JPEG", (700, 200)), ("JPEG", (200, 600))])
def test_images_keep_orientation_and_visible_pixels(stitch, format, size):
    item = file("image." + ("png" if format == "PNG" else "jpeg"))
    image = Image.new("RGB", size, (220, 30, 40))
    output = BytesIO()
    image.save(output, format=format)
    stitch.inputs[item.s3uripath] = output.getvalue()
    assert stitch.run([item])["stitchedoutput"]["stichedfilecount"] == 1
    with fitz.open(stream=next(iter(stitch.uploads.values())), filetype="pdf") as doc:
        assert len(doc) == 1
        assert (doc[0].rect.width > doc[0].rect.height) == (size[0] > size[1])
        pix = doc[0].get_pixmap()
        assert min(pix.samples) < 60
        assert doc[0].get_images()


def test_widget_is_flattened_visibly_and_plain_page_survives(stitch):
    item = file("form.pdf")
    data = pdf_bytes("FORM PAGE", "PLAIN PAGE", widget=True)
    stitch.inputs[item.s3uripath] = data
    stitch.run([item])
    with fitz.open(stream=next(iter(stitch.uploads.values())), filetype="pdf") as doc, fitz.open(stream=data, filetype="pdf") as original:
        assert len(doc) == 2
        assert "PLAIN PAGE" in doc[1].get_text()
        assert not list(doc[0].widgets())
        # Field is rasterized: rendered ink in its rectangle must survive.
        rect = fitz.Rect(60, 100, 400, 150)
        before = original[0].get_pixmap(clip=rect, colorspace=fitz.csGRAY)
        after = doc[0].get_pixmap(clip=rect, colorspace=fitz.csGRAY)
        assert sum(v < 180 for v in after.samples) > 200
        assert abs(sum(before.samples) - sum(after.samples)) / (255 * len(before.samples)) < 0.03


@pytest.mark.parametrize("names", [[], ["bad.pdf"], ["attachment.txt"]])
def test_empty_and_all_invalid_have_no_stitched_output(stitch, names):
    files = [file(n) for n in names]
    stitch.inputs.update({f.s3uripath: b"malformed" for f in files})
    result = stitch.run(files)
    assert result["stitchedoutput"] is None
    assert not stitch.uploads
    assert len(result["filestozip"]) == int("attachment.txt" in names)
