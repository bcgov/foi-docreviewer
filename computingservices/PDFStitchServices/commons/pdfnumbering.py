from io import BytesIO
import os

from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from pypdf import PdfReader, PdfWriter
import os

position_to_width = {
    "left": 10,
    "center": 38,
    "right": 50,
}
w, h = letter
filepath = os.path.dirname(os.path.abspath(__file__)) +"/fonts/BCSans-Bold.ttf"
pdfmetrics.registerFont(TTFont('BC-Sans', filepath))
textcolor=colors.HexColor("#38598A")

def add_numbering_to_pdf(original_pdf, paginationtext="", position="right", start_page=1, end_page=None,
                         start_index=1, size=14, font="BC-Sans") -> bytes:
    """Adds numbering to pdf file"""   
    original_pdf_bytes = PdfReader(original_pdf)
    parameters = get_parameters_for_numbering(original_pdf_bytes,paginationtext, position, start_page, end_page, start_index, size, font)
    empty_numbered_pdf = create_empty_numbered_pdf(**parameters)
    return merge_pdf_pages(original_pdf_bytes, empty_numbered_pdf)


def get_parameters_for_numbering(original_pdf,paginationtext, position, start_page, end_page, start_index, size, font) -> dict:
    """Setting parameters for numbering"""
    return {
        "paginationtext": paginationtext,
        "width_of_pages": get_width_of_pages(original_pdf, position),
        "height": 70.5 * mm,
        "start_page": start_page - 1,
        "end_page": end_page or len(original_pdf.pages) + 1,
        "start_index": start_index,
        "size": size,
        "font": font,
        "number_of_pages": len(original_pdf.pages),
    }


def get_width_of_pages(original_pdf, position) -> list:
    """Returns width of pages"""

    width_of_pages = []
    for index in range(len(original_pdf.pages)):
        ratio = original_pdf.pages[index].mediabox.width/200
        width = position_to_width[position] * ratio * mm
        width_of_pages.append(width)
    return width_of_pages


def create_empty_numbered_pdf(paginationtext, width_of_pages, height, start_page, end_page, start_index, size, font,
                              number_of_pages) -> PdfReader:
    """Returns empty pdf file with numbering only"""
    empty_canvas = canvas.Canvas("empty_canvas.pdf", pagesize=letter)
    for index in range(number_of_pages):
        empty_canvas.rotate(90) 
        empty_canvas.setFont(font, size)
        empty_canvas.setFillColor(textcolor)
        if index in range(start_page, end_page):
            number = paginationtext.replace("[x]", str(index - start_page + start_index)).replace("[totalpages]", str(number_of_pages)).upper()
            empty_canvas.drawString((width_of_pages[index] - 175), -(h-height), number)
        else:
            empty_canvas.drawString(width_of_pages[index], height, "")
        empty_canvas.showPage()
    return PdfReader(BytesIO(empty_canvas.getpdfdata()))


def merge_pdf_pages(first_pdf, second_pdf) -> bytes:
    """Returns file with combined pages of first and second pdf"""
    writer = PdfWriter()
    print("range(first_pdf.getNumPages()) >> ", len(first_pdf.pages))
    for number_of_page in range(len(first_pdf.pages)):
        page_of_first_pdf = first_pdf.pages[number_of_page]
        page_of_second_pdf = second_pdf.pages[number_of_page]
        page_of_first_pdf.merge_page(page_of_second_pdf)
        writer.add_page(page_of_first_pdf)
    result = BytesIO()
    writer.write(result)
    return result.getvalue()