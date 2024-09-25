from . import getdbconnection, gets3credentialsobject
from . import foidedupehashcalulator
from psycopg2 import sql
from os import path
from copy import deepcopy
import json
import psycopg2
import requests
from aws_requests_auth.aws_auth import AWSRequestsAuth
from pypdf import PdfReader, PdfWriter
from io import BytesIO
from html import escape
import hashlib
import uuid
import boto3
from botocore.config import Config
from re import sub
import fitz
import PyPDF2
from utils import (
    gets3credentialsobject,
    getdedupeproducermessage,
    dedupe_s3_region,
    dedupe_s3_host,
    dedupe_s3_service,
    dedupe_s3_env,
    request_management_api,
    file_conversion_types
)
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib import colors
from reportlab.lib.colors import Color
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib import utils
import os
import textwrap
from PyPDF2.generic import ArrayObject, NameObject, TextStringObject, DictionaryObject, NumberObject, FloatObject

# Get the directory of the current Python file (inside the 'service' folder)
service_folder_path = os.path.dirname(os.path.abspath(__file__))

# Navigate to the parent directory (common folder)
common_folder_path = os.path.dirname(service_folder_path)

# Construct the path to the 'utils' folder
utils_folder_path = os.path.join(common_folder_path, "utils")

# Now get the path to the 'BCSans-Bold.ttf' font file inside the 'utils' folder
font_path = os.path.join(utils_folder_path, "fonts", "BCSans-Regular_2f.ttf")

print(f"Font path: {font_path}")

pdfmetrics.registerFont(TTFont('BC-Sans', font_path))
textcolor=colors.HexColor("#38598A")
aw, ah = A4
lw, lh = letter

def __getcredentialsbybcgovcode(bcgovcode):
    _conn = getdbconnection()
    s3cred = None
    try:
        cur = _conn.cursor()
        _sql = sql.SQL(
            "SELECT  attributes FROM {0} WHERE bucket='{1}'and category='Records'".format(
                'public."DocumentPathMapper"',
                "{0}-{1}-e".format(bcgovcode.lower(), dedupe_s3_env.lower()),
            )
        )
        cur.execute(_sql)
        attributes = cur.fetchone()
        if attributes is not None:
            s3cred = gets3credentialsobject(str(attributes[0]))
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if _conn is not None:
            _conn.close()
            print("Database connection closed.")

    return s3cred

def _prepareattachment(producermessage, data, s3uripath, file_name):
    attachment = {
        "filename": escape(sub("<[0-9]+>", "", file_name, 1)),
        "s3uripath": s3uripath,
        "attributes": deepcopy(producermessage.attributes),
    }
    attachment["attributes"]["filesize"] = len(data)
    attachment["attributes"][
        "parentpdfmasterid"
    ] = producermessage.documentmasterid
    attachment["attributes"].pop("batch")
    attachment["attributes"].pop("extension")
    attachment["attributes"].pop("incompatible")
    return attachment

def _generate_file_attachments(producermessage, reader, auth):
    file_attachments = []
    for page in reader.pages:
        if "/Annots" in page:
            annotations = page["/Annots"]
            for annotation in annotations:
                subtype = annotation.get_object()["/Subtype"]
                if subtype == "/FileAttachment":
                    # Placeholder logic to handle pdf attachments+embedds. Once resources available to revise feature, and extract attachments + embedds into one new parent PDF, this error handling will be removed.
                    raise Exception("PDF contains attachments and/or embedded files. File must be manually fixed and replaced")

                    # Old logic to extract embedded files. Uncomment when new feature to save pdf embedds + attachemnts as one file is started.
                    # producermessage.attributes["hasattachment"] = True
                    # fileobj = annotation.get_object()["/FS"]
                    # file = fileobj["/F"]
                    # data = fileobj["/EF"]["/F"].get_data()
                    # # data = BytesIO(data).getvalue()
                    # s3uripath = (
                    #     path.splitext(producermessage.s3filepath)[0]
                    #     + "/"
                    #     + "{0}{1}".format(uuid.uuid4(), path.splitext(file)[1])
                    # )
                    # uploadresponse = requests.put(s3uripath, data=data, auth=auth)
                    # uploadresponse.raise_for_status()
                    # attachment = _prepareattachment(producermessage, data, s3uripath, file)
                    # file_attachments.append(attachment)
    return file_attachments

# New function to split comments into pages
def split_comments_to_pages(comments,font,font_size, canvas, lines_per_page=50):
    pages = []
    current_page = []
    for comment in comments:
        print("\n Each comment:",comment)
        if 'text' in comment:
            comment_text = f"{comment['text']}"
            #comment_text = f"Page {comment['page']}: {comment['text']}\n"
            # Wrap the text to fit within the page width
            wrapped_lines = wrap_text(comment_text, width=500, font=font, font_size=font_size, canvas=canvas)
            for line in wrapped_lines:
                current_page.append(line)
                if len(current_page) >= lines_per_page:
                    pages.append(current_page)
                    current_page = []   
    if current_page:  # Add any remaining comments to the last page
        pages.append(current_page)    
    print("pages-split_comments_to_pages:",pages)
    return pages


def wrap_text(text, width, font, font_size, canvas):
    """
    This function wraps text into lines based on the available width.
    """
    wrapped_lines = []
    line = ""    
    text_width = canvas.stringWidth(text, font, font_size)
    if text_width <= width:
        line = text
    else:
        words = text.split(" ")
        for word in words:
            # Check the width of the line with the current word
            line_width = canvas.stringWidth(line + word + " ", font, font_size)
            if line_width <= width:
                line += word + " "
            else:
                #If the word doesn't fit, append the current line and start a new one
                if line:
                    print("line::",line)
                    wrapped_lines.append(line)  # Append current line
                line = ""  # Reset line
                # Handle long words that need to be broken up
                while canvas.stringWidth(word, font, font_size) > width:
                    # Find the largest part of the word that fits within the width
                    for i in range(1, len(word) + 1):
                        part = word[:i]
                        if canvas.stringWidth(part, font, font_size) > width:
                            # Append the part that fits and continue with the remaining part
                            wrapped_lines.append(word[:i - 1])  # Add the part that fits
                            word = word[i - 1:]  # Remaining part of the word
                            break

                # Add the remaining part of the word to the line
                line = word + " "
    # Append the last line
    if line:
        wrapped_lines.append(line)
    print("\nwrapped_lines:",wrapped_lines)
    return wrapped_lines

def _clearmetadata(response, pagecount, reader, s3_access_key_id,s3_secret_access_key,filepath,auth):
    # clear metadata
    reader2 = PyPDF2.PdfReader(BytesIO(response.content))
    # Check if metadata exists.
    if reader2.metadata is not None:
        # Create a new PDF file without metadata.
        writer = PyPDF2.PdfWriter()
        # Copy pages from the original PDF to the new PDF.
        for page_num in range(len(reader.pages)):
            page = reader2.pages[page_num]                
            try:
                #Function to get all comments type annotations & copy it to a new page
                pagecount, writer= createpagesforcomments(page, page_num, writer, reader2, pagecount)
            except Exception as e:
                print(f"Error in creating new page with comment annotations: {e}")
        buffer = BytesIO()
        writer.write(buffer)
        try:
            # Now, flatten the PDF content using the __flattenfitz function
            flattened_buffer = __flattenfitz(buffer.getvalue())
        except Exception as e:
            print(f"Error in flatenning pdf: {e}")

        client = boto3.client('s3',config=Config(signature_version='s3v4'),
            endpoint_url='https://{0}/'.format(dedupe_s3_host),
            aws_access_key_id= s3_access_key_id,
            aws_secret_access_key= s3_secret_access_key,
            region_name= dedupe_s3_region
        )
        copyresponse = client.copy_object(
            CopySource="/" + "/".join(filepath.split("/")[3:]), # /Bucket-name/path/filename
            Bucket=filepath.split("/")[3], # Destination bucket
            Key= "/".join(filepath.split("/")[4:])[:-4] + 'ORIGINAL' + '.pdf' # Destination path/filename
        )
        uploadresponse = requests.put(
            filepath,
            data= flattened_buffer.getvalue(), #buffer.getvalue(),
            auth=auth
        )
        uploadresponse.raise_for_status()

    return pagecount

def __flattenfitz(docbytesarr):
    doc = fitz.open(stream=BytesIO(docbytesarr))
    out = fitz.open()  # output PDF
    for page in doc:
        w, h = page.rect.br  # page width / height taken from bottom right point coords
        outpage = out.new_page(width=w, height=h)  # out page has same dimensions
        pix = page.get_pixmap(dpi=150)  # set desired resolution
        outpage.insert_image(page.rect, pixmap=pix)

    # Saving the flattened PDF to a buffer
    buffer = BytesIO()
    out.save(buffer, garbage=3, deflate=True)
    buffer.seek(0)  # Reset the buffer to the beginning
    return buffer

def __renderannotationsascontent(annotation_obj, subtype, c, updated_annotations):
    if subtype in ["/Highlight", "/Squiggly"]:
        rect = annotation_obj[NameObject("/Rect")]
        x1, y1, x2, y2 = [float(coord) for coord in rect]
        # Extract the highlight color from the /C key
        if "/C" in annotation_obj:
            highlight_color = annotation_obj.get("/C", [1, 1, 0])
            r, g, b = [float(c) for c in highlight_color]
            # Normalize RGB values if needed
            r = min(max(r, 0), 1)
            g = min(max(g, 0), 1)
            b = min(max(b, 0), 1)
        # Extract the opacity (if available)
        if "/CA" in annotation_obj:
            opacity = float(annotation_obj.get("/CA", 1.0))  # Opacity value
            c.setFillAlpha(opacity)  # Set transparency
        # Use setFillAlpha to apply the opacity
        c.setFillColor(Color(r, g, b))  
        c.rect(x1, y1, x2 - x1, y2 - y1, stroke=0, fill=1)   
    elif subtype == "/FreeText":
        rect = annotation_obj[NameObject("/Rect")]
        x1, y1, x2, y2 = [float(coord) for coord in rect]
        # Check if it's a callout annotation (look for the /IT and /L properties)
        if "/IT" in annotation_obj and annotation_obj[NameObject("/IT")] == "/FreeTextCallout":
            # Draw the leader line (usually stored in /L)
            if "/L" in annotation_obj:
                leader_line = annotation_obj[NameObject("/L")]
                lx1, ly1, lx2, ly2 = [float(coord) for coord in leader_line]

                # Draw the leader line
                c.setStrokeColor(Color(1, 0, 0))  # Set the color for the callout leader line
                c.setLineWidth(1.5)
                c.line(lx1, ly1, lx2, ly2)  # Draw the line from start to end points

            # Draw the text inside the box defined by /Rect
            c.setFillColor(Color(0, 0, 0))  # Set the color for the text (black)
            c.setFont("Helvetica", 10)
            c.drawString(x1 + 5, y2 - 10, annotation_obj.get("/Contents", ""))  # Adjust text placement

            # Draw the callout box
            c.setStrokeColor(Color(1, 0, 0))  # Set stroke color for the box (red)
            c.rect(x1, y1, x2 - x1, y2 - y1, stroke=1, fill=0)  # Draw rectangle around the text

        # For generic /FreeText (non-callout) annotations
        else:
            c.setFillColor(Color(0, 0, 0))  # Set the color for the text (black)
            c.setFont("Helvetica", 10)
            c.drawString(x1 + 5, y2 - 10, annotation_obj.get("/Contents", ""))  # Draw the text


    # elif subtype == "/StrikeOut":
    #     rect = annotation_obj[NameObject("/Rect")]
    #     if len(rect) == 4:
    #         x1, y1, x2, y2 = [float(coord) for coord in rect]
    #         c.setStrokeColor(Color(1, 0, 0))  # Default red color
    #         c.setLineWidth(2)
    #         c.line(x1, (y1 + y2) / 2, x2, (y1 + y2) / 2)
     
    elif subtype in ["/Underline", "/StrikeOut"]:
        # Handle Underline Annotations
        rect = annotation_obj.get("/Rect", [0, 0, 0, 0])
        x1, y1, x2, y2 = [float(coord) for coord in rect]
        c.setLineWidth(1)
        color = annotation_obj.get("/C", [1, 1, 0])
        r, g, b = [float(c) for c in color]
        c.setStrokeColor(Color(r, g, b))
        c.line(x1, (y1 + y2) / 2, x2, (y1 + y2) / 2)
        #c.line(x1, y1 - 2, x2, y1 - 2)  # Draw a line just below the text position

    elif subtype in ["/Square"] and "/C" in annotation_obj:
        # Handle Sticky Note Annotations (often drawn as squares with color)
        rect = annotation_obj.get("/Rect", [0, 0, 0, 0])
        x1, y1, x2, y2 = [float(coord) for coord in rect]
        sticky_note_color = annotation_obj.get("/C", [1, 1, 0])
        r, g, b = [float(c) for c in sticky_note_color]
        c.setFillColor(Color(r, g, b))
        c.rect(x1, y1, x2 - x1, y2 - y1, fill=1, stroke=0)

    elif subtype == "/Circle":
        rect = annotation_obj[NameObject("/Rect")]
        x1, y1, x2, y2 = [float(coord) for coord in rect]
        radius_x = (x2 - x1) / 2
        radius_y = (y2 - y1) / 2
        # Extract the border color from the /C key (defaults to black if /C is missing)
        if "/C" in annotation_obj:
            border_color = annotation_obj[NameObject("/C")]
            r, g, b = [float(c) for c in border_color]  # Extract RGB values
        c.setStrokeColor(Color(r, g, b))
        c.setLineWidth(2)
        c.ellipse(x1, y1, x2, y2, stroke=1, fill=0) 

    # Caret Annotations (insertion caret)
    elif subtype == "/Caret":
        rect = annotation_obj[NameObject("/Rect")]
        x1, y1, x2, y2 = [float(coord) for coord in rect]
        color = annotation_obj.get("/C", [1, 1, 0])
        r, g, b = [float(c) for c in color]
        c.setStrokeColor(Color(r, g, b))
        c.line(x1, y1, x2, y2)  # Draw caret (insertion point)
    # Stamp Annotations (visual stamp)
    elif subtype == "/Stamp":
        rect = annotation_obj[NameObject("/Rect")]
        x1, y1, x2, y2 = [float(coord) for coord in rect]

        # Try drawing at the top of the rectangle, slightly above
        stamp_name = annotation_obj.get("/Name", "Stamp")

        # Debugging: Print stamp name and coordinates
        print(f"Stamp Name: {stamp_name}")
        print(f"x1: {x1}, y2 + 10: {y2 + 10}")

        # Set font (fallback to Helvetica if BC-Sans is not registered)
        try:
            c.setFont("BC-Sans", 12)
        except:
            c.setFont("Helvetica", 12)  # Fallback if BC-Sans is not available

        # Draw the stamp name
        c.drawString(x1, y2 + 10, f"[Stamp: {stamp_name}]")


    elif subtype == "/Ink" and "/InkList" in annotation_obj:
        # Handle Ink Annotations
        inklist = annotation_obj.get("/InkList", [])
        # Create a Path object for the ink strokes
        path = c.beginPath()
        color = annotation_obj.get("/C", [1, 1, 0])
        r, g, b = [float(c) for c in color]
        c.setStrokeColor(Color(r,g,b))
        c.setLineWidth(2)
        # Use Bezier curves to smooth the ink paths
        for stroke in inklist:
            points = list(map(float, stroke))
            if len(points) >= 4:
                path.moveTo(points[0], points[1])  # Move to the first point
                for i in range(2, len(points) - 2, 2):
                    # Draw a smooth curve using Bezier
                    x0, y0 = points[i], points[i + 1]
                    x1, y1 = points[i + 2], points[i + 3]
                    path.curveTo(x0, y0, x0, y0, x1, y1)
            else:
                path.moveTo(points[0], points[1])  # Start point
                for i in range(2, len(points), 2):
                    path.lineTo(points[i], points[i + 1])  # Connect the points
        c.drawPath(path, stroke=1)
    elif subtype in ["/Polygon", "/PolyLine"]:
        path = c.beginPath()
        c.setLineWidth(2)
        if "/C" in annotation_obj:
            line_color = annotation_obj[NameObject("/C")]
            r, g, b = [float(c) for c in line_color]
        else:
            r, g, b = 0, 0, 0  # Default black
        c.setStrokeColor(Color(r, g, b))
        vertices = annotation_obj[NameObject("/Vertices")]
        path.moveTo(vertices[0], vertices[1])
        for i in range(2, len(vertices), 2):
            path.lineTo(vertices[i], vertices[i + 1])
        if subtype == "/Polygon":
            path.lineTo(vertices[0], vertices[1])  # Close the polygon
        c.drawPath(path, stroke=1)


    if subtype != "/Widget":
        annotation_obj = DictionaryObject()
    updated_annotations.append(annotation_obj)
    return updated_annotations, c

def __rendercommentsonnewpage(comments,pagecount,writer,parameters):
    try:
        comments_pdf = BytesIO()
        c = canvas.Canvas(comments_pdf, pagesize=letter)
        font = parameters.get("font")
        font_size = parameters.get("fontsize")       
        width = parameters.get("width")
        height = parameters.get("height")
        currentpagesize = (width, height)
        comment_pages = split_comments_to_pages(comments, font, font_size, c, lines_per_page=50)
        for comment_page in comment_pages:
            text = c.beginText(40, 750)
            text.setFont(font, font_size)
            for line in comment_page:
                text.textLine(line)
            c.setPageSize(currentpagesize)
            c.drawText(text)
            c.showPage()
            pagecount += 1
        c.save()
        comments_pdf.seek(0)
        comments_pdf_reader = PyPDF2.PdfReader(comments_pdf)
        writer.add_page(comments_pdf_reader.pages[0])  # Add comments as a new page
        return pagecount,writer
    except Exception as e:
        print(f"Error in rendering comments on new page in pdf: {e}")

def createpagesforcomments(page, page_num, writer, reader2, pagecount):
    # Check if the page contains annotations
    if "/Annots" in page:
        comments = []
        annotations = page["/Annots"]
        # Create a new PDF overlay with reportlab to draw annotation content
        annotation_overlay = BytesIO()
        c = canvas.Canvas(annotation_overlay, pagesize=letter)
        pagenum=page_num + 1
        for annot in annotations:
            annotation_obj = annot.get_object()
            subtype = annotation_obj["/Subtype"]
            print("\nAnnotation Object:", annotation_obj)
            #Flatten comments - collect all the annots
            if subtype == "/Text" and "/Contents" in annotation_obj:
                comment = annotation_obj["/Contents"]
                comments.append({
                    'page': pagenum,#page_num + 1,
                    'text': comment
                })
        # Finalize annotation overlay for the page
        c.save()
        annotation_overlay.seek(0)
        # Merge the overlay (annotations rendered as static) onto the original PDF page
        overlay_pdf = PyPDF2.PdfReader(annotation_overlay)
        if len(overlay_pdf.pages) > 0:
            overlay_page = overlay_pdf.pages[0]
            page.merge_page(overlay_page)
        writer.add_page(page)
        if comments:
            try:
                parameters = get_page_properties(reader2, page_num)
                # If there are comments, create an additional page for them
                pagecount,writer=__rendercommentsonnewpage(comments,pagecount,writer,parameters)
            except Exception as e:
                print(f"Error in rendering comments on new page in pdf: {e}")
    else:
        writer.add_page(page)
    return pagecount, writer

def gets3documenthashcode(producermessage):
    s3credentials = __getcredentialsbybcgovcode(producermessage.bcgovcode)    
    s3_access_key_id = s3credentials.s3accesskey
    s3_secret_access_key = s3credentials.s3secretkey
    auth = AWSRequestsAuth(
        aws_access_key=s3_access_key_id,
        aws_secret_access_key=s3_secret_access_key,
        aws_host=dedupe_s3_host,
        aws_region=dedupe_s3_region,
        aws_service=dedupe_s3_service,
    )

    pagecount = 1
    _filename, extension = path.splitext(producermessage.filename)
    filepath = producermessage.s3filepath
    producermessage.attributes = json.loads(producermessage.attributes)
    if extension.lower() not in [".pdf"] and not (
        producermessage.attributes.get("isattachment", False)
        and producermessage.trigger == "recordreplace"
    ):
        filepath = path.splitext(filepath)[0] + extension
    response = requests.get("{0}".format(filepath), auth=auth, stream=True)
    reader = None

    if extension.lower() in [".pdf"] or (
        producermessage.attributes.get("isattachment", False) and producermessage.trigger == "recordreplace"
        ):
        reader = PdfReader(BytesIO(response.content))
        
        # "No of pages in {0} is {1} ".format(_filename, len(reader.pages)))
        pagecount = len(reader.pages)
        attachments = []
        if reader.attachments:
            if "/Collection" in reader.trailer["/Root"]:
                producermessage.attributes["isportfolio"] = True
            else:
                # Placeholder logic to handle pdf attachments+embedds. Once resources available to revise feature, and extract attachments + embedds into one new parent PDF, this error handling will be removed.
                raise Exception("PDF contains attachments and/or embedded files. File must be manually fixed and replaced")
            
                # Old logic to extract attached files. Uncomment when new feature to save pdf embedds + attachemnts as one file is started.
                # producermessage.attributes["hasattachment"] = True
            for name in reader.attachments:
                s3uripath = (
                    path.splitext(filepath)[0]
                    + "/"
                    + "{0}{1}".format(uuid.uuid4(), path.splitext(name)[1])
                )
                data = b"".join(reader.attachments[name])
                uploadresponse = requests.put(s3uripath, data=data, auth=auth)
                uploadresponse.raise_for_status()
                attachment = _prepareattachment(producermessage, data, s3uripath, name)
                attachments.append(attachment)
            saveresponse = requests.post(
                request_management_api
                + "/api/foirecord/-1/ministryrequest/"
                + producermessage.ministryrequestid,
                data=json.dumps({"records": attachments}),
                headers={
                    "Authorization": producermessage.usertoken,
                    "Content-Type": "application/json",
                },
            )
            saveresponse.raise_for_status()

        # New logic to extract embedded file attachments (classified under annotations in the PDF) from pages in PDF
        # Before looping of pdf pages started; confirm if annotations exist in the pdf using pyMuPdf library (fitz)
        fitz_reader = fitz.open(stream=BytesIO(response.content), filetype="pdf")
        if (fitz_reader.has_annots()):
            file_attachments = _generate_file_attachments(producermessage, reader, auth)
            if (len(file_attachments) > 0):
                saveresponse = requests.post(
                    request_management_api
                    + "/api/foirecord/-1/ministryrequest/"
                    + producermessage.ministryrequestid,
                    data=json.dumps({"records": file_attachments}),
                    headers={
                        "Authorization": producermessage.usertoken,
                        "Content-Type": "application/json",
                    }
                )
                saveresponse.raise_for_status()   
        fitz_reader.close()
        # clear metadata
        try:
            pagecount= _clearmetadata(response, pagecount, reader, s3_access_key_id,s3_secret_access_key,filepath,auth)
        except Exception as e:
            print(f"Exception while clearing metadata/flattening: {e}")
               
    elif extension.lower() in file_conversion_types:
        # "Extension different {0}, so need to download pdf here for pagecount!!".format(extension))
        pdfresponseofconverted = requests.get(
            "{0}".format(producermessage.s3filepath), auth=auth, stream=True
        )
        reader = PdfReader(BytesIO(pdfresponseofconverted.content))
        # "Converted PDF , No of pages in {0} is {1} ".format(_filename, len(reader.pages)))
        pagecount = len(reader.pages)

    if reader:
        BytesIO().close()
        reader.stream.close()
    sig = hashlib.sha1()
    for line in response.iter_lines():
        sig.update(line)

    return (sig.hexdigest(), pagecount)


def get_page_properties(original_pdf, pagenum, font="BC-Sans") -> dict:
    """Setting parameters for numbering"""
    width = original_pdf.pages[pagenum].mediabox.width  
    height = original_pdf.pages[pagenum].mediabox.height
    if height < 450:
        fontsize=10
    else:
        fontsize=12
    return {
        "width": width,
        "height": height,
        "fontsize": fontsize,
        "font": font,
        "numberofpages": len(original_pdf.pages),
    }

def get_original_pdf_page_details(original_pdf):
    width_of_pages = []
    height_of_pages = []
    fontsize = []
    
    for index in range(len(original_pdf.pages)):
        width = original_pdf.pages[index].mediabox.width  
        height = original_pdf.pages[index].mediabox.height
        width_of_pages.append(width)        
        height_of_pages.append(height)
        if height < 450:
            fontsize.append(10)
        else:
            fontsize.append(12)

    return width_of_pages, height_of_pages, fontsize



# def gets3documenthashcode(producermessage):
#     s3credentials = __getcredentialsbybcgovcode(producermessage.bcgovcode)    
#     s3_access_key_id = s3credentials.s3accesskey
#     s3_secret_access_key = s3credentials.s3secretkey
#     auth = AWSRequestsAuth(
#         aws_access_key=s3_access_key_id,
#         aws_secret_access_key=s3_secret_access_key,
#         aws_host=dedupe_s3_host,
#         aws_region=dedupe_s3_region,
#         aws_service=dedupe_s3_service,
#     )

#     pagecount = 1
#     _filename, extension = path.splitext(producermessage.filename)
#     filepath = producermessage.s3filepath
#     producermessage.attributes = json.loads(producermessage.attributes)
#     if extension.lower() not in [".pdf"] and not (
#         producermessage.attributes.get("isattachment", False)
#         and producermessage.trigger == "recordreplace"
#     ):
#         filepath = path.splitext(filepath)[0] + extension
#     response = requests.get("{0}".format(filepath), auth=auth, stream=True)
#     reader = None

#     if extension.lower() in [".pdf"] or (
#         producermessage.attributes.get("isattachment", False) and producermessage.trigger == "recordreplace"
#         ):
#         reader = PdfReader(BytesIO(response.content))
        
#         # "No of pages in {0} is {1} ".format(_filename, len(reader.pages)))
#         pagecount = len(reader.pages)
#         attachments = []
#         if reader.attachments:
#             if "/Collection" in reader.trailer["/Root"]:
#                 producermessage.attributes["isportfolio"] = True
#             else:
#                 # Placeholder logic to handle pdf attachments+embedds. Once resources available to revise feature, and extract attachments + embedds into one new parent PDF, this error handling will be removed.
#                 raise Exception("PDF contains attachments and/or embedded files. File must be manually fixed and replaced")
            
#                 # Old logic to extract attached files. Uncomment when new feature to save pdf embedds + attachemnts as one file is started.
#                 # producermessage.attributes["hasattachment"] = True
#             for name in reader.attachments:
#                 s3uripath = (
#                     path.splitext(filepath)[0]
#                     + "/"
#                     + "{0}{1}".format(uuid.uuid4(), path.splitext(name)[1])
#                 )
#                 data = b"".join(reader.attachments[name])
#                 uploadresponse = requests.put(s3uripath, data=data, auth=auth)
#                 uploadresponse.raise_for_status()
#                 attachment = _prepareattachment(producermessage, data, s3uripath, name)
#                 attachments.append(attachment)
#             saveresponse = requests.post(
#                 request_management_api
#                 + "/api/foirecord/-1/ministryrequest/"
#                 + producermessage.ministryrequestid,
#                 data=json.dumps({"records": attachments}),
#                 headers={
#                     "Authorization": producermessage.usertoken,
#                     "Content-Type": "application/json",
#                 },
#             )
#             saveresponse.raise_for_status()

#         # New logic to extract embedded file attachments (classified under annotations in the PDF) from pages in PDF
#         # Before looping of pdf pages started; confirm if annotations exist in the pdf using pyMuPdf library (fitz)
#         fitz_reader = fitz.open(stream=BytesIO(response.content), filetype="pdf")
#         if (fitz_reader.has_annots()):
#             file_attachments = _generate_file_attachments(producermessage, reader, auth)
#             if (len(file_attachments) > 0):
#                 saveresponse = requests.post(
#                     request_management_api
#                     + "/api/foirecord/-1/ministryrequest/"
#                     + producermessage.ministryrequestid,
#                     data=json.dumps({"records": file_attachments}),
#                     headers={
#                         "Authorization": producermessage.usertoken,
#                         "Content-Type": "application/json",
#                     }
#                 )
#                 saveresponse.raise_for_status()        
#         fitz_reader.close()
        
#         # clear metadata
#         reader2 = PyPDF2.PdfReader(BytesIO(response.content))
#         # Check if metadata exists.
#         if reader2.metadata is not None:
#             # Create a new PDF file without metadata.
#             writer = PyPDF2.PdfWriter()
#             # Copy pages from the original PDF to the new PDF.
#             for page_num in range(len(reader.pages)):
#                 page = reader2.pages[page_num]                
#                 writer.add_page(page)        
#             #writer.remove_links() # to remove comments.
#             buffer = BytesIO()
#             writer.write(buffer)
#             client = boto3.client('s3',config=Config(signature_version='s3v4'),
#                 endpoint_url='https://{0}/'.format(dedupe_s3_host),
#                 aws_access_key_id= s3_access_key_id,
#                 aws_secret_access_key= s3_secret_access_key,
#                 region_name= dedupe_s3_region
#             )
#             copyresponse = client.copy_object(
#                 CopySource="/" + "/".join(filepath.split("/")[3:]), # /Bucket-name/path/filename
#                 Bucket=filepath.split("/")[3], # Destination bucket
#                 Key= "/".join(filepath.split("/")[4:])[:-4] + 'ORIGINAL' + '.pdf' # Destination path/filename
#             )
#             uploadresponse = requests.put(
#                 filepath,
#                 data=buffer.getvalue(),
#                 auth=auth
#             )
#             uploadresponse.raise_for_status()

#     elif extension.lower() in file_conversion_types:
#         # "Extension different {0}, so need to download pdf here for pagecount!!".format(extension))
#         pdfresponseofconverted = requests.get(
#             "{0}".format(producermessage.s3filepath), auth=auth, stream=True
#         )
#         reader = PdfReader(BytesIO(pdfresponseofconverted.content))
#         # "Converted PDF , No of pages in {0} is {1} ".format(_filename, len(reader.pages)))
#         pagecount = len(reader.pages)

#     if reader:
#         BytesIO().close()
#         reader.stream.close()
#     sig = hashlib.sha1()
#     for line in response.iter_lines():
#         sig.update(line)

#     return (sig.hexdigest(), pagecount)
