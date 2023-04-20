from io import BytesIO
import logging
import os
import gc

from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from pypdf import PdfReader, PdfWriter

filepath = os.path.dirname(os.path.abspath(__file__)) +"/fonts/BCSans-Bold.ttf"
pdfmetrics.registerFont(TTFont('BC-Sans', filepath))
textcolor=colors.HexColor("#38598A")
aw, ah = A4
lw, lh = letter

def add_numbering_to_pdf(original_pdf, paginationtext="", start_page=1, end_page=None,
                         start_index=1, font="BC-Sans") -> bytes:
    """Adds numbering to pdf file"""   
    original_pdf_bytes = PdfReader(original_pdf)
    empty_numbered_pdf_bytes = None
    try:
        parameters = get_parameters_for_numbering(original_pdf_bytes,paginationtext, start_page, end_page, start_index, font)
        empty_numbered_pdf_bytes = create_empty_numbered_pdf(parameters)
        return merge_pdf_pages(original_pdf_bytes, empty_numbered_pdf_bytes)
    except(Exception) as error:
        logging.error('Error in creating the numbered pdf.')
        logging.error(error)
        raise
    finally:
        #original_pdf_bytes = None
        #empty_numbered_pdf_bytes = None
        #del original_pdf_bytes
        original_pdf_bytes.stream.close()
        del original_pdf_bytes
        empty_numbered_pdf_bytes.stream.close()
        del empty_numbered_pdf_bytes
        gc.collect()


def get_parameters_for_numbering(original_pdf, paginationtext, start_page, end_page, start_index, font) -> dict:
    """Setting parameters for numbering"""

    width_of_pages, height_of_pages, x_value_of_pages, y_value_of_pages, fontsize = get_original_pdf_page_details(original_pdf)
    return {
        "paginationtext": paginationtext,
        "original_width_of_pages": width_of_pages,
        "original_height_of_pages": height_of_pages,
        "xvalue":x_value_of_pages,
        "yvalue":y_value_of_pages,
        "start_page": start_page - 1,
        "end_page": end_page or len(original_pdf.pages) + 1,
        "start_index": start_index,
        "size": fontsize,
        "font": font,
        "number_of_pages": len(original_pdf.pages),
    }

def get_original_pdf_page_details(original_pdf):
    width_of_pages = []
    height_of_pages = []
    x_value_of_pages = []
    y_value_of_pages = []
    fontsize = []
    
    for index in range(len(original_pdf.pages)):
        width = original_pdf.pages[index].mediabox.width  
        height = original_pdf.pages[index].mediabox.height   
        width_of_pages.append(width)        
        height_of_pages.append(height)

        if width < height:
            x = (height/2) - 70
        else:
            #landscape pages
            x = (height/2) - 115
        x_value_of_pages.append(x)

        if width == round(aw,4) and height == round(ah,4):
            y = (width - 12)
        elif width == round(lw,4) and height == round(lh,4):
            y = (width - 52)
        else:
            y = (width - 10)
        y_value_of_pages.append(y)

        if height < 450:
            fontsize.append(10)
        else:
            fontsize.append(14)

    return width_of_pages, height_of_pages, x_value_of_pages, y_value_of_pages, fontsize

def create_empty_numbered_pdf(parameters):
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
    try:
        number_canvas = canvas.Canvas("empty_canvas.pdf")    
        for index in range(number_of_pages):
            currentpagesize = (original_width_of_pages[index], original_height_of_pages[index])
            print("currentpagesize = ",currentpagesize)
            print("(x, y)) = ", (xvalue[index], -(yvalue[index])))
            number_canvas.setPageSize(currentpagesize)
            number_canvas.rotate(90)
            number_canvas.setFont(font, size[index])
            number_canvas.setFillColor(textcolor)

            if index in range(start_page, end_page):
                number = paginationtext.replace("[x]", str(index - start_page + start_index)).replace("[totalpages]", str(number_of_pages)).upper()
                number_canvas.drawString(xvalue[index], -(yvalue[index]), number)
            
            number_canvas.showPage()
        return PdfReader(BytesIO(number_canvas.getpdfdata()))
    except(Exception) as error:
            logging.error('Error with creating the numbered pdf.')
            logging.error(error)
            raise


def merge_pdf_pages(first_pdf, second_pdf) -> bytes:
    """Returns file with combined pages of first and second pdf"""
    result = BytesIO()
    writer = PdfWriter()
    try:        
        print("len second_pdf = ", len(second_pdf.pages))
        for number_of_page in range(len(first_pdf.pages)):
            page_of_first_pdf = first_pdf.pages[number_of_page]
            page_of_second_pdf = second_pdf.pages[number_of_page]
            text = page_of_second_pdf.extract_text()
            print("text = ", text) 
            stream = page_of_first_pdf.get_contents().get_object()
            for s in stream:
                print("Object:",s.get_object())
                print("Type:",type(s.get_object()))
                try:
                    print("Data:",type(s.get_object().get_data()))
                except Exception as err:
                    print(str(err))
                    continue
            if "/Type" in page_of_first_pdf.keys() and page_of_first_pdf["/Type"] == "/Page" and "/Type" in page_of_second_pdf.keys() and page_of_second_pdf["/Type"] == "/Page":
                page_of_first_pdf.merge_page(page_of_second_pdf)
            else:
                print("********* pass ***********")
                # handle the case where one or both of the objects is not a PDF page
                # pass
            writer.add_page(page_of_first_pdf)        
        writer.write(result)
        return result.getvalue()
    except(Exception) as error:
            logging.error('Error with adding number to the stitched pdf.')
            logging.error(error)
            raise
    finally:
        #data = result.getvalue()
        # release the reference to the data
        #memoryview(data).release()
        result.close()
        # first_pdf = None
        # second_pdf = None
        # writer = None
        # del writer
        writer.close()
        first_pdf.stream.close()
        del first_pdf
        second_pdf.stream.close()
        del second_pdf
        gc.collect()
