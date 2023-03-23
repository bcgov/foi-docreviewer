from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from io import StringIO, BytesIO
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.utils import ImageReader


# Using ReportLab to insert image into PDF
def getimagepdf(raw_image_bytes):
    imgtemp = BytesIO()
    empty_canvas = canvas.Canvas(imgtemp)
    image = ImageReader(BytesIO(raw_image_bytes))
    iw, ih = image.getSize()
    print("Image W >>> ", iw)
    print("Image H >>> ", ih)
    # Draw image on Canvas and save PDF in buffer
    empty_canvas.drawImage(image, 160, 160, 399, 760, preserveAspectRatio=True)    ## at (399,760) with size 160x160
    empty_canvas.save()
    print("******DrawImage******")
    overlay = PdfReader(BytesIO(imgtemp.getvalue()))
    print("overlay pages >>> ", len(overlay.pages))
    return overlay