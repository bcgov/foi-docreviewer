from io import BytesIO
import os

from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from pypdf import PdfReader, PdfWriter, PdfMerger
import os

filepath = os.path.dirname(os.path.abspath(__file__)) +"/fonts/BCSans-Bold.ttf"
pdfmetrics.registerFont(TTFont('BC-Sans', filepath))
textcolor=colors.HexColor("#38598A")
aw, ah = A4

def add_numbering_to_pdf(original_pdf, paginationtext="", start_page=1, end_page=None,
                         start_index=1, size=14, font="BC-Sans") -> bytes:
    """Adds numbering to pdf file"""   
    original_pdf_bytes = PdfReader(original_pdf)
    parameters = get_parameters_for_numbering(original_pdf_bytes,paginationtext, start_page, end_page, start_index, size, font)
    return create_empty_numbered_pdf_and_merge_pages(original_pdf_bytes, parameters)


def get_parameters_for_numbering(original_pdf, paginationtext, start_page, end_page, start_index, size, font) -> dict:
    """Setting parameters for numbering"""
    return {
        "paginationtext": paginationtext,
        "original_width_of_pages": get_original_width_of_pages(original_pdf),
        "original_height_of_pages": get_original_height_of_pages(original_pdf),
        "xvalue":get_x_value(original_pdf),
        "yvalue":get_y_value(original_pdf),
        "start_page": start_page - 1,
        "end_page": end_page or len(original_pdf.pages) + 1,
        "start_index": start_index,
        "size": size,
        "font": font,
        "number_of_pages": len(original_pdf.pages),
    }

def get_x_value(original_pdf) -> list:
    """Returns X value for the pages"""
    x_value_of_pages = []
    for index in range(len(original_pdf.pages)):
        original_w = original_pdf.pages[index].mediabox.width
        original_h = original_pdf.pages[index].mediabox.height
        if original_w < original_h:
            x = (original_h/2) - 70
        else:
            #landscape pages
            x = (original_h/2) - 115
        x_value_of_pages.append(x)
    return x_value_of_pages

def get_y_value(original_pdf) -> list:
    """Returns Y value for the pages"""

    y_value_of_pages = []
    for index in range(len(original_pdf.pages)):
        original_w = original_pdf.pages[index].mediabox.width
        original_h = original_pdf.pages[index].mediabox.height
        # mostly image pages
        if original_w == round(aw,4) and original_h == round(ah,4):
            y = (original_w - 12)
        else:
            y = (original_w - 10)
        y_value_of_pages.append(y)
    return y_value_of_pages

def get_original_width_of_pages(original_pdf) -> list:
    """Returns width of pages"""

    width_of_pages = []
    for index in range(len(original_pdf.pages)):
        width = original_pdf.pages[index].mediabox.width     
        width_of_pages.append(width)
    return width_of_pages

def get_original_height_of_pages(original_pdf)-> list:
    height_of_pages = []
    for index in range(len(original_pdf.pages)):
        height = original_pdf.pages[index].mediabox.height
        height_of_pages.append(height)
    return height_of_pages

def create_empty_numbered_pdf_and_merge_pages(original_pdf_bytes, parameters):
    """Returns empty pdf file with numbering only"""

    number_of_pages = parameters.get("number_of_pages")
    original_width_of_pages = parameters.get("original_width_of_pages")
    original_height_of_pages = parameters.get("original_height_of_pages")
    font = parameters.get("font")
    size = parameters.get("size")
    start_page = parameters.get("start_page")
    end_page = parameters.get("end_page")
    paginationtext = parameters.get("paginationtext")
    start_index = parameters.get("start_index")
    xvalue = parameters.get("xvalue")
    yvalue = parameters.get("yvalue")
    merger = PdfMerger()
    final_array = []
    for index in range(number_of_pages):
        pagesize = (original_width_of_pages[index], original_height_of_pages[index])
        # creating the canvas for each page based on the pagesize
        empty_canvas = canvas.Canvas("empty_canvas.pdf", pagesize=pagesize)
        empty_canvas.rotate(90) 
        empty_canvas.setFont(font, size)
        empty_canvas.setFillColor(textcolor)
        if index in range(start_page, end_page):
            number = paginationtext.replace("[x]", str(index - start_page + start_index)).replace("[totalpages]", str(number_of_pages)).upper()
            empty_canvas.drawString(xvalue[index], -(yvalue[index]), number)
        empty_canvas.showPage()
        final_array.append(BytesIO(empty_canvas.getpdfdata()))

    merge_numbered_pdf_bytes(final_array, merger)
    if merger:
        with BytesIO() as bytes_stream:
            merger.write(bytes_stream)
            bytes_stream.seek(0)
            return merge_pdf_pages(original_pdf_bytes, PdfReader(bytes_stream)) 

def merge_numbered_pdf_bytes(final_array, merger):
    for pdf_bytes in final_array:
        merger.append(PdfReader(pdf_bytes))

def merge_pdf_pages(first_pdf, second_pdf) -> bytes:
    """Returns file with combined pages of first and second pdf"""
    writer = PdfWriter()
    for number_of_page in range(len(first_pdf.pages)):
        print("number_of_page = ", number_of_page)
        page_of_first_pdf = first_pdf.pages[number_of_page]
        page_of_second_pdf = second_pdf.pages[number_of_page]
        text = page_of_second_pdf.extract_text()
        print("merge_pdf_pages = ", text)
        page_of_first_pdf.merge_page(page_of_second_pdf)
        writer.add_page(page_of_first_pdf)
    result = BytesIO()
    writer.write(result)
    return result.getvalue()
