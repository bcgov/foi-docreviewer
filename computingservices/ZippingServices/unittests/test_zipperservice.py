"""Characterize archive contracts before changing the runtime."""
from io import BytesIO
import zipfile

import PyPDF2
import pytest
from reportlab.pdfgen import canvas


@pytest.mark.parametrize("names", [[], ["notes.txt"], ["nested/folder/with spaces.txt", "café/文件.txt"], ["same.txt", "same.txt"]])
def test_archive_crc_order_and_non_pdf_fidelity(archive, names):
    entries = [(name, "https://synthetic/" + str(i), bytes(range(256)) + str(i).encode()) for i, name in enumerate(names)]
    if len(names) != len(set(names)):
        with pytest.warns(UserWarning, match="Duplicate name"):
            state = archive(entries)
    else:
        state = archive(entries)
    with zipfile.ZipFile(BytesIO(state.uploads[0][1])) as result:
        assert result.testzip() is None
        assert result.namelist() == names
        assert [result.read(info) for info in result.infolist()] == [entry[2] for entry in entries]
    assert [(s["version"], s["status"], s["isziping"]) for s in state.statuses] == [
        (3, "zippingstarted", True), (4, "zippingcompleted", True), (5, "completed", False)]
    assert state.paths[0][1:] == ("2", "harms", "synthetic")


@pytest.mark.parametrize("category,folder,phase,want,stored", [
    ("harms", None, None, "Harms/SYN-001.zip", "harms"),
    ("redline", "My FOLDER", None, "My folder/SYN-001.zip", "redline"),
    ("responsepackage_phase1", None, "1", "Responsepackage_phase1/SYN-001.zip", "responsepackagephase1"),
])
def test_folder_capitalization_and_phase_persistence(archive, message, category, folder, phase, want, stored):
    message.category, message.foldername, message.phase = category, folder, phase
    state = archive([])
    assert state.uploads[0][0] == want
    assert state.paths[0][2] == stored


def labeled_pdf():
    output = BytesIO()
    c = canvas.Canvas(output)
    c.setAuthor("Synthetic author")
    c.setTitle("Synthetic title")
    c.drawString(60, 700, "SYNTHETIC FIRST PAGE")
    c.linkURL("https://example.invalid", (60, 680, 200, 710))
    c.acroForm.textfield(name="synthetic-field", value="form value", x=60, y=600)
    c.showPage()
    c.drawString(60, 700, "SYNTHETIC SECOND PAGE")
    c.save()
    reader = PyPDF2.PdfReader(BytesIO(output.getvalue()))
    writer = PyPDF2.PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.pages[1].rotate(90)
    writer.add_metadata({"/Author": "Synthetic author", "/Title": "Synthetic title"})
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_pdf_retains_text_rotation_and_annotations_but_drops_document_metadata(archive):
    data = labeled_pdf()
    state = archive([("document.pdf", "https://synthetic/document.PDF", data)])
    with zipfile.ZipFile(BytesIO(state.uploads[0][1])) as result:
        rewritten = result.read("document.pdf")
    reader = PyPDF2.PdfReader(BytesIO(rewritten))
    assert len(reader.pages) == 2
    assert [page.extract_text().strip() for page in reader.pages] == ["SYNTHETIC FIRST PAGE", "SYNTHETIC SECOND PAGE"]
    assert reader.pages[1].get("/Rotate") == 90
    assert reader.metadata.get("/Author") is None and reader.metadata.get("/Title") is None
    annotations = [a.get_object() for a in reader.pages[0]["/Annots"]]
    assert any(a.get("/A", {}).get("/URI") == "https://example.invalid" for a in annotations)
    assert any(a.get("/T") == "synthetic-field" and a.get("/V") == "form value" for a in annotations)


@pytest.mark.parametrize("protected", [False, True])
def test_unreadable_pdf_falls_back_to_original_bytes(archive, protected):
    data = b"not a pdf"
    if protected:
        writer = PyPDF2.PdfWriter()
        writer.add_blank_page(100, 100)
        writer.encrypt("synthetic-password")
        output = BytesIO()
        writer.write(output)
        data = output.getvalue()
    state = archive([("input.pdf", "https://synthetic/input.pdf", data)])
    with zipfile.ZipFile(BytesIO(state.uploads[0][1])) as result:
        assert result.read("input.pdf") == data


@pytest.mark.parametrize("error,versions", [("download", [3, 5]), ("upload", [3, 5])])
def test_exceptions_record_error_without_persisting_package(archive, error, versions):
    # Get shared capture state before configuring the next call.
    state = archive([])
    state.statuses.clear(); state.paths.clear(); state.uploads.clear()
    state.error = error
    state = archive([("x.txt", "https://synthetic/x.txt", b"content")])
    assert [s["version"] for s in state.statuses] == versions
    assert state.statuses[-1]["status"] == "error"
    assert not state.paths


def test_false_upload_result_records_zipper_error(archive):
    state = archive([])
    state.statuses.clear(); state.paths.clear()
    state.result = False
    archive([])
    assert [(s["version"], s["status"]) for s in state.statuses] == [(3, "zippingstarted"), (4, "zippingcompleted"), (5, "error")]
    assert state.statuses[-1]["isziping"] is True
    assert not state.paths
