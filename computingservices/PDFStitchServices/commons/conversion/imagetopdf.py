from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from io import StringIO, BytesIO
from reportlab.lib.pagesizes import A4, landscape, portrait
from reportlab.lib.utils import ImageReader


# Using ReportLab to insert image into PDF
def getimagepdf(raw_image_bytes):
    imgtemp = BytesIO()
    image = ImageReader(BytesIO(raw_image_bytes))
    iw, ih = A4
    empty_canvas = canvas.Canvas(imgtemp, pagesize=A4)
    
    # Draw image on Canvas and save PDF in buffer
    # empty_canvas.drawImage(image, 160, 160, 399, 760, preserveAspectRatio=True)    ## at (399,760) with size 160x160
    empty_canvas.drawImage(image, 0, ih - 150, preserveAspectRatio=True)
    empty_canvas.save()
    overlay = PdfReader(BytesIO(imgtemp.getvalue()))
    return overlay

def convertimagetopdf(image_bytes):
    try:
        imgtemp = BytesIO()

        # Create a canvas and set the dimensions to match the image
        image = ImageReader(BytesIO(image_bytes))
        print("convert bytes to image completed")
        
        image_width, image_height = image.getSize()
        
        print("image size: ",(image_width, image_height))

        c_image_width = image_width + 25
        c_image_height = image_height + 25

        if c_image_height < 280:
            c_image_height = 280
        if image_width > image_height:            
            c = canvas.Canvas(imgtemp, pagesize=landscape((c_image_width, c_image_height)))
            print("if")
        else:
            c = canvas.Canvas(imgtemp, pagesize=portrait((c_image_width, c_image_height)))
            print("else")
        print("before drawImage")        
        c.drawImage(image, 0, 0, image_width, image_height)
        print("completed drawImage")
        # Save the canvas to a PDF file
        c.save()
        print("completed save")
        overlay = PdfReader(BytesIO(imgtemp.getvalue()))
        print("get the reader")
        return overlay
    except(Exception) as error:
        print("Error in converting image to pdf, error: ", error)  
