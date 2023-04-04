from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from io import StringIO, BytesIO
from reportlab.lib.pagesizes import A4, letter
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

    imgtemp = BytesIO()

    # Create a canvas and set the dimensions to match the image
    img = ImageReader(BytesIO(image_bytes))
    img_width, img_height = img.getSize()
    canvas = canvas.Canvas(imgtemp, pagesize=(img_width, img_height))

    # Calculate the scaling factor to fit the image onto the canvas
    canvas_width, canvas_height = canvas._pagesize
    aspect_ratio = img_width / img_height
    canvas_aspect_ratio = canvas_width / canvas_height

    if aspect_ratio > canvas_aspect_ratio:
        scaling_factor = canvas_width / img_width
    else:
        scaling_factor = canvas_height / img_height

    # Draw the image onto the canvas
    canvas.drawImage(img, 0, 0, img_width * scaling_factor, img_height * scaling_factor)

    # Save the PDF file
    canvas.save()

    overlay = PdfReader(BytesIO(imgtemp.getvalue()))
    return overlay
