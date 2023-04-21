from io import BytesIO
import logging
import os
import fitz

from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from pypdf import PdfReader, PdfWriter

filepath = os.path.dirname(os.path.abspath(__file__)) +"/fonts/BCSans-Bold.ttf"
color_hex = "#38598A"
aw, ah = A4
lw, lh = letter

def add_numbering_to_pdf(original_pdf, paginationtext="", start_page=1, end_page=None,
                         start_index=1, font="BC-Sans") -> bytes:
    try:
        """Adds numbering to pdf file"""   
        # original_pdf_bytes = PdfReader(original_pdf)
        print("add_numbering_to_pdf")
        original_pdf_bytes = fitz.Document(stream=original_pdf, filetype="pdf")
        parameters = get_parameters_for_numbering(original_pdf_bytes,paginationtext, start_page, end_page, start_index, font)

        number_of_pages = parameters.get("number_of_pages")
        font = parameters.get("font")
        size = parameters.get("size")  
        paginationtext = parameters.get("paginationtext")

        output_buffer = BytesIO()
        doc =  fitz.Document(stream=original_pdf, filetype="pdf")      
        # Iterate through each page
        for i, page in enumerate(doc):
            # Get the width and height of the current page
            w, h = page.bound().width, page.bound().height
            print("(w, h) = ", (w, h))
            
            print("iswrapped? = ", page.is_wrapped)
            if not page.is_wrapped:
                page.wrap_contents()

            pagetext = paginationtext.replace("[x]", str(i + 1)).replace("[totalpages]", str(number_of_pages)).upper()
            print("textvalue = ", pagetext)

            fontsize = size[i]
            textsize = len(pagetext) + fontsize
            # print("textsize = ", textsize)
            
            x =  w-10
            y = (h/2) + (textsize)
            print("text pos (x, y) = ", (round(x,2), round(y,2)))
            pos = fitz.Point(round(x,2), round(y,2))
            font_color = (int(color_hex[1:3], 16)/255, int(color_hex[3:5], 16)/255, int(color_hex[5:7], 16)/255)
            page.insert_text(pos, pagetext, fontsize=fontsize, rotate=90, color=font_color)

        doc.save(output_buffer)
        # Close the input PDF
        doc.close()
        output_buffer.seek(0)
        # Return the output buffer containing the generated PDF
        return output_buffer.getvalue()
    except(Exception) as error:
        #logging.error('Error with divisional stitch.')
        logging.error(error)
    finally:
        del original_pdf_bytes
        del original_pdf
        output_buffer.close()

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
        "end_page": end_page or original_pdf.page_count + 1,
        "start_index": start_index,
        "size": fontsize,
        "font": font,
        "number_of_pages": original_pdf.page_count,
    }

def get_original_pdf_page_details(original_pdf):
    width_of_pages = []
    height_of_pages = []
    x_value_of_pages = []
    y_value_of_pages = []
    fontsize = []
    
    for index in range(original_pdf.page_count):
        page = original_pdf[index]
        width = page.rect.width  
        height = page.rect.height

        width_of_pages.append(width)        
        height_of_pages.append(height)

        x = get_original_pdf_x_value(width, height)
        x_value_of_pages.append(x)

        y = get_original_pdf_y_value(height)
        y_value_of_pages.append(y)

        if height < 450:
            fontsize.append(10)
        else:
            fontsize.append(12)

    return width_of_pages, height_of_pages, x_value_of_pages, y_value_of_pages, fontsize

def get_original_pdf_x_value(width, height):
    if width < height:
        return (height/2) - 70
    #landscape pages
    return (height/2) - 115

def get_original_pdf_y_value(height):
    if height == round(ah,4):
        return (height/2) + 50
    elif height == round(lh,4):
        if isinstance(height, float):
            return (height/2) + 50
        else:
            return (height/2) + 20
    return (height/2)