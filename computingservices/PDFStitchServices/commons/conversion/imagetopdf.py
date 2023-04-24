from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, portrait
from reportlab.lib.utils import ImageReader


def convertimagetopdf(image_bytes):
    try:
        # Create a canvas and set the dimensions to match the image
        image = ImageReader(BytesIO(image_bytes))
        image_width, image_height = image.getSize()

        c_image_width = image_width + 25
        c_image_height = max(image_height + 25, 420)
        pagesize = landscape((c_image_width, c_image_height)) if image_width > image_height else portrait((c_image_width, c_image_height))

        with BytesIO() as output:
            c = canvas.Canvas(output, pagesize=pagesize)
            c.drawImage(image, 0, 0, image_width, image_height)
            c.save()
            overlay = output.getvalue()

        return overlay

    except Exception as e:
        print("Error in converting image to PDF:", e)
        raise