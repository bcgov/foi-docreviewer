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