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
print(filepath)
# font_file = os.path.dirname(os.path.abspath(__file__)) +"/fonts/BCSans-Bold.ttf"
# font = fitz.Font(font_file)

# font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
# font_file = os.path.join(font_path, "BCSans-Bold.ttf")

# print(font_file)
# font_name = "BC-Sans"

# # Add font directory to search path
# fitz.add_font(font_path)

# # Initialize font object
# font = fitz.Font(font_file, fontname=font_name)

textcolor=colors.HexColor("#38598A")
aw, ah = A4
lw, lh = letter

def add_numbering_to_pdf(original_pdf, paginationtext="", start_page=1, end_page=None,
                         start_index=1, font="BC-Sans") -> bytes:
    """Adds numbering to pdf file"""   
    # original_pdf_bytes = PdfReader(original_pdf)
    print("add_numbering_to_pdf")
    original_pdf_bytes = fitz.Document(stream=original_pdf, filetype="pdf")
    parameters = get_parameters_for_numbering(original_pdf_bytes,paginationtext, start_page, end_page, start_index, font)

    number_of_pages = parameters.get("number_of_pages")
    font = parameters.get("font")
    size = parameters.get("size")  
    paginationtext = parameters.get("paginationtext")
    xvalue = parameters.get("xvalue")
    yvalue = parameters.get("yvalue")

    output_buffer = BytesIO()
    doc =  fitz.Document(stream=original_pdf, filetype="pdf")      
    # Iterate through each page
    for i, page in enumerate(doc):
         # Get the width and height of the current page
        w, h = page.bound().width, page.bound().height
        print("(w, h) = ", (w, h))
        print("(xvalue[i], yvalue[i]) = ", (xvalue[i], yvalue[i]))

        text = paginationtext.replace("[x]", str(i + 1)).replace("[totalpages]", str(number_of_pages)).upper()
        print("textvalue = ", text)
        fontsize = size[i]
        pos = fitz.Point(w-15, yvalue[i])
        color_hex = "#38598A"
        font_color = (int(color_hex[1:3], 16)/255, int(color_hex[3:5], 16)/255, int(color_hex[5:7], 16)/255)
        page.insert_text(pos, text, fontsize=fontsize, rotate=90, color=font_color)
    doc.save(output_buffer)
    # Close the input PDF
    doc.close()
    output_buffer.seek(0)
    # Return the output buffer containing the generated PDF
    return output_buffer.getvalue()

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
    
    # for index in range(len(original_pdf.pages)):
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
            fontsize.append(14)

    return width_of_pages, height_of_pages, x_value_of_pages, y_value_of_pages, fontsize

def get_original_pdf_x_value(width, height):
    if width < height:
        return (height/2) - 70
    #landscape pages
    return (height/2) - 115

def get_original_pdf_y_value(height):
    if height == round(ah,4):
        print("if")
        return (height/2) + 50
    elif height == round(lh,4):
        if isinstance(height, float):
            print("isinstance")
            return (height/2) + 50
        else:
            print("else")
            return (height/2) + 20
    print("return")
    return (height/2)

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
            number_canvas.setPageSize(currentpagesize)
            number_canvas.rotate(90)
            number_canvas.setFont(font, size[index])
            number_canvas.setFillColor(textcolor)

            if index in range(start_page, end_page):
                number = paginationtext.replace("[x]", str(index + 1)).replace("[totalpages]", str(number_of_pages)).upper()
                number_canvas.drawString(xvalue[index], -(yvalue[index]), number)
            
            number_canvas.showPage()
        return PdfReader(BytesIO(number_canvas.getpdfdata()))
    except(Exception) as error:
            logging.error('Error with creating the numbered pdf.')
            logging.error(error)


def merge_pdf_pages_test(second_pdf) -> bytes:
    """Returns file with combined pages of first and second pdf"""
    writer = PdfWriter()
    for page in second_pdf.pages:
        text = page.extract_text()
        print("merge_pdf_pages_test = ", text)
        writer.add_page(page)
    result = BytesIO()
    writer.write(result)
    return result.getvalue()


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
            if "/Type" in page_of_first_pdf.keys() and page_of_first_pdf["/Type"] == "/Page" and "/Type" in page_of_second_pdf.keys() and page_of_second_pdf["/Type"] == "/Page":
                try:
                    page_of_first_pdf.merge_page(page_of_second_pdf)
                except Exception as err:
                    print(str(err))
                    stream = page_of_first_pdf.get_contents().get_object()
                    for s in stream:
                        print("Object:",s.get_object())
                        print("Type:",type(s.get_object()))
                        try:
                            print("Data:",type(s.get_object().get_data()))
                        except Exception as err:
                            print(str(err))
                            stream = None
                            continue
                    stream = None
                    continue
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
