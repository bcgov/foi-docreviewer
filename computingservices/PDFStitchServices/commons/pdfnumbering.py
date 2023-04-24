from io import BytesIO
import logging
import os
import fitz

filepath = os.path.dirname(os.path.abspath(__file__)) +"/fonts/BCSans-Bold.ttf"
color_hex = "#38598A"

def add_numbering_to_pdf(original_pdf, paginationtext="") -> bytes:
    """Adds numbering to pdf file"""   
    doc = None
    output_buffer = BytesIO()

    try:

        doc =  fitz.Document(stream=original_pdf, filetype="pdf")
        number_of_pages = doc.page_count

        # Iterate through each page
        for i, page in enumerate(doc):
            # Get the width and height of the current page
            w, h = page.bound().width, page.bound().height
            
            if not page.is_wrapped:
                page.wrap_contents()

            pagetext = paginationtext.replace("[x]", str(i + 1)).replace("[totalpages]", str(number_of_pages)).upper()

            if h < 450:
                fontsize = 10
            else:
                fontsize = 12
            textsize = len(pagetext) + fontsize
            
            x =  w-10
            y = (h/2) + (textsize)
            pos = fitz.Point(round(x,2), round(y,2))

            font_color = (int(color_hex[1:3], 16)/255, int(color_hex[3:5], 16)/255, int(color_hex[5:7], 16)/255)

            page.insert_text(pos, pagetext, fontsize=fontsize, rotate=90, color=font_color)
            page = None
        doc.save(output_buffer)
        
        output_buffer.seek(0)
        # Return the output buffer containing the generated PDF
        return output_buffer.getvalue()
    except(Exception) as error:
        logging.error(error)
    finally:
        if doc:
            doc.close()
        if output_buffer:
            output_buffer.close()
        original_pdf = None