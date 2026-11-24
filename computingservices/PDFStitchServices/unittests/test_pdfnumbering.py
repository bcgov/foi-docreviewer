import fitz
import pytest

from commons import add_numbering_to_pdf


@pytest.mark.parametrize("width,height,rotation", [(612, 792, 0), (792, 612, 0), (612, 792, 90), (300, 400, 0)])
def test_active_numbering_preserves_content_and_page_count(width, height, rotation):
    with fitz.open() as source:
        for label in ["ORIGINAL ONE", "ORIGINAL TWO"]:
            page = source.new_page(width=width, height=height)
            page.insert_text((30, 40), label)
            page.set_rotation(rotation)
        data = add_numbering_to_pdf(source.tobytes(), paginationtext="page [x] of [totalpages]")
    with fitz.open(stream=data, filetype="pdf") as doc:
        assert len(doc) == 2
        for i, page in enumerate(doc):
            assert ["ORIGINAL ONE", "ORIGINAL TWO"][i] in page.get_text()
            assert page.rotation == rotation
            if rotation:
                # Baseline writes outside the unrotated crop on this input.
                page.set_cropbox(fitz.Rect(0, 0, 612, 792))
                assert "PAGE" not in page.get_text()
            else:
                assert f"PAGE {i + 1} OF 2" in page.get_text()
