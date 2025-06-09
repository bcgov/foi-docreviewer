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
import maya
import pytz
from utils import (
    gets3credentialsobject,
    getdedupeproducermessage,
    dedupe_s3_region,
    dedupe_s3_host,
    dedupe_s3_service,
    dedupe_s3_env,
    request_management_api,
    file_conversion_types,
    needs_ocr,
    has_fillable_forms,
)
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.pagesizes import letter
import os
from decimal import Decimal

# Get the directory of the current Python file (inside the 'service' folder)
service_folder_path = os.path.dirname(os.path.abspath(__file__))
# Navigate to the parent directory (common folder)
common_folder_path = os.path.dirname(service_folder_path)
# Construct the path to the 'utils' folder & get the path to the 'BCSans-Bold.ttf' font file inside the 'utils' folder
utils_folder_path = os.path.join(common_folder_path, "utils")
font_path = os.path.join(utils_folder_path, "fonts", "BCSans-Regular_2f.ttf")
pdfmetrics.registerFont(TTFont('BC-Sans', font_path))


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
    
    try:
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
                    current_page.append({'pageno': comment['page'], 'text':line, 'commentnumber':comment['commentnumbypage'],
                                        'author':comment['author'], 'subject':comment['subject'], 'creationdate':comment['creationdate']})
                    if len(current_page) >= lines_per_page:
                        pages.append(current_page)
                        current_page = []   
        if current_page:  # Add any remaining comments to the last page
            pages.append(current_page)    
        print("pages-split_comments_to_pages:",pages)
        return pages
    except Exception as e:
        print(f"Error in splitting comments by pages: {e}")



def wrap_text(text, width, font, font_size, canvas):
    """
    This function wraps text into lines based on the available width.
    """
    try:
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
        return wrapped_lines
    except Exception as e:
        print(f"Error in wrapping the text comments in each page: {e}")

def _clearmetadata(response, pagecount, reader, s3_access_key_id,s3_secret_access_key,filepath,auth,filename):
    # clear metadata
    reader2 = PyPDF2.PdfReader(BytesIO(response.content)) 
    _hasannotations = has_annotations(reader)   
    # Check if metadata exists.
    if reader2.metadata is not None or _hasannotations:
        # Create a new PDF file without metadata.
        writer = PyPDF2.PdfWriter()
        # Copy pages from the original PDF to the new PDF.
        for page_num in range(len(reader.pages)):
            page = reader2.pages[page_num]   
            try:
                #Function to get all comments type annotations & copy it to a new page
                pagecount, writer= createpagesforcomments(page, page_num, writer, reader2, pagecount,filename)
            except Exception as e:
                print(f"Error in creating new page with comment annotations: {e}")
        buffer = BytesIO()
        writer.write(buffer)
        flattened_buffer = buffer
        try:
            # Now, flatten the PDF content using the __flattenfitz function
            if _hasannotations:
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
    doc = fitz.open(stream=BytesIO(docbytesarr), filetype="pdf")
    out = fitz.open()  # output PDF
    for page_num in range(len(doc)):
        #page = doc[page_num]
        page = doc.load_page(page_num) 
        print("\nPage:",page)
        widget_exist = page.first_widget is not None
        w, h = page.rect.br  # page width and height
        # Create a new page in the output document with the same size
        outpage = out.new_page(width=w, height=h)
        # Render the page text (keeping it searchable)
        outpage.show_pdf_page(page.rect, doc, page_num)
        # Manually process each annotation
        annot = page.first_annot
        if widget_exist:
            print("\nwidget_exist:",widget_exist)
            pix = page.get_pixmap(dpi=150)  # set desired resolution
            outpage.insert_image(page.rect, pixmap=pix)

        while annot:
            try:
                annot_rect = annot.rect  # Get the annotation's rectangle
                # Check for invalid annotation dimensions (zero width/height)
                if __is_not_rect_renderable(annot_rect):
                    print(f"Skipping annotation on page {page_num + 1}: Invalid annotation dimensions.")
                    annot = annot.next  # Move to the next annots & skip invalid ones
                    continue
                # Handle specific case of highlight annotations
                if annot.type[0] == 8:  # Highlight annotations
                    # Create a slightly larger rect to ensure the highlight covers the text
                    #print(f'x0={annot_rect.x0}, y0={annot_rect.y0} , x1={annot_rect.x}, y1={annot_rect.y1}')
                    expanded_rect = fitz.Rect(
                        annot_rect.x0 - 1, annot_rect.y0 - 1, 
                        annot_rect.x1 + 1, annot_rect.y1 + 1
                    ) 
                    # Render the annotation (highlight) as an image
                    annot_pix = page.get_pixmap(clip=annot_rect, dpi=150)                  
                    # Burn the annotation (highlight) into the page with adjusted rect
                    outpage.insert_image(expanded_rect, pixmap=annot_pix)
                else:
                    # For other types of annotations, use the original rect
                    annot_pix = page.get_pixmap(clip=annot_rect, dpi=150)
                    outpage.insert_image(annot_rect, pixmap=annot_pix)  # Burn annotation
            except Exception as e:
                print(f"Error processing annotation on page {page_num + 1}: {e}")
            annot = annot.next  # Move to the next annotation
    # Saving the flattened PDF to a buffer
    buffer = BytesIO()
    out.save(buffer, garbage=3, deflate=True)
    buffer.seek(0)  # Reset the buffer to the beginning
    return buffer

def __is_not_rect_renderable(rect: fitz.Rect) -> bool:
    return (
        not rect.is_valid or
        rect.is_empty or
        rect.is_infinite or
        rect.width <= 0 or
        rect.height <= 0
)


def __rendercommentsonnewpage(comments,pagecount,writer,parameters,filename):
    try:
        comments_pdf = BytesIO()
        c = canvas.Canvas(comments_pdf, pagesize=letter)
        font = parameters.get("font")
        font_size = parameters.get("fontsize")   
        title_font_size = parameters.get("title_fontsize", font_size + 4)    
        width = parameters.get("width")
        height = parameters.get("height")
        rotation= parameters.get("rotation")
        print("rotation:",rotation)
        #set standard A4 size for new page if page have rotation
        if rotation not in [0, 360]:
            width=612
            height=792
        currentpagesize = (width, height)
        print("\ncurrentpagesize:",currentpagesize)
        title_height=height-40
        comment_pages = split_comments_to_pages(comments, font, font_size, c, lines_per_page=50)
        for comment_page in comment_pages:
            print("\ncomment_page:",comment_page)
            c.setFont(font, title_font_size)
            #c.setFont("Helvetica", 12)
            c.drawString(40, title_height, f"Summary of Comments on {filename}")
            # Draw a line left to right under the title
            c.setLineWidth(2)
            c.line(40, title_height-10, width - 40, title_height-10)
            c.drawString(40, title_height-25, f"Page: {comment_page[0]['pageno']}")
            c.line(40, title_height-30, width - 40, title_height-30)
            text = c.beginText(40, title_height-45)
            text.setFont(font, font_size)
            for line in comment_page:
                number = line['commentnumber']
                text_content = line['text']
                author = line.get('author', 'N/A') 
                subject= line["subject"]
                creationdate = line.get('creationdate', 'N/A')
                # Define fixed widths for the columns
                number_column_width = 10
                subject_column_width = 20
                creationdate_column_width = 10
                formatted_line = (f"Number: {str(number):<{number_column_width}}"
                      f"Author: {author:<{number_column_width}}"
                      f"Subject: {subject:<{subject_column_width}}"
                      f"Date: {creationdate:<{creationdate_column_width}}")
                text.textLine(formatted_line)
                current_y = text.getY() 
                line_y = current_y + 10
                c.setLineWidth(1)
                c.line(40, line_y, width-45, line_y)
                text.textLine(text_content)
                text.textLine('')
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

def has_annotations(reader):
    """
    Check if the PDF has any annotations.
    """
    for page_num in range(len(reader.pages)):
        page = reader.pages[page_num]
        if "/Annots" in page:
            return True
    return False

def createpagesforcomments(page, page_num, writer, reader2, pagecount,filename):
    # Check if the page contains annotations
    if "/Annots" in page:
        comments = []
        annotations = page["/Annots"]
        # Create a new PDF overlay with reportlab to draw annotation content
        annotation_overlay = BytesIO()
        c = canvas.Canvas(annotation_overlay, pagesize=letter)
        annot_num = 1  # Start numbering annotations
        for annot in annotations:
            annotation_obj = annot.get_object()
            #subtype = annotation_obj["/Subtype"]
            #print("\nAnnotation Object:", annotation_obj)
            #Flatten comments - collect all the annots with content
            if "/Contents" in annotation_obj:
                comment = annotation_obj["/Contents"]
                author = annotation_obj["/T"] if "/T" in annotation_obj else ""
                subject = annotation_obj["/Subj"] if "/Subj" in annotation_obj else ""
                annotationdate=annotation_obj["/CreationDate"] if "/CreationDate" in annotation_obj else ""
                creationdate= __converttoPST(annotationdate) if annotationdate else ""
                comments.append({
                    'page': page_num + 1,
                    'text': comment,
                    'commentnumbypage':annot_num,
                    'author':author,
                    'subject':subject,
                    'creationdate':creationdate
                })
                if "/Rect" in annotation_obj:
                    annot_rect = annotation_obj["/Rect"]
                    # Rectangle coordinates, format: [x1, y1, x2, y2]
                    number_x = float(annot_rect[2].get_object()) + 5  # Slightly to the right of the annotation
                    number_y = float(annot_rect[3].get_object()) - 5  # Slightly above the annotation
                    # Define the size of the box
                    box_width = 10 
                    box_height = 10
                    # Calculate position of box to centre the number
                    box_x = number_x - (box_width / 2)  
                    box_y = number_y - (box_height / 2)
                    # Draw box around the number
                    c.rect(box_x, box_y, box_width, box_height, stroke=1, fill=0)
                    c.setFont("BC-Sans", 8)
                    text = str(annot_num)                 
                    # Get text width and height for centering
                    text_width = c.stringWidth(text, "BC-Sans", 8)
                    text_height = 8
                    # Center the number horizontally and vertically within the box
                    text_x = box_x + (box_width - text_width) / 2
                    text_y = box_y + (box_height - text_height) / 2 + 2
                    # Draw the number
                    c.drawString(text_x, text_y, text)
                    annot_num += 1  # Increment the annotation number
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
                pagecount,writer=__rendercommentsonnewpage(comments,pagecount,writer,parameters,filename)
            except Exception as e:
                print(f"Error in rendering comments on new page in pdf: {e}")
    else:
        #print("**NO Annotations here!!")
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
        # check to see if pdf file needs ocr service
        #ocr_needed = verify_ocr_needed(response.content, producermessage)
        # clear metadata
        try:
            filenamewithextension=_filename+extension.lower()
            pagecount= _clearmetadata(response, pagecount, reader, s3_access_key_id,s3_secret_access_key,filepath,auth,filenamewithextension)
        except Exception as e:
            print(f"Exception while clearing metadata/flattening: {e}")
               
    elif extension.lower() in file_conversion_types:
        # "Extension different {0}, so need to download pdf here for pagecount!!".format(extension))
        pdfresponseofconverted = requests.get(
            "{0}".format(producermessage.s3filepath), auth=auth, stream=True
        )
        reader = PdfReader(BytesIO(pdfresponseofconverted.content))
        # check to see if converted pdf file needs ocr service
        #ocr_needed = verify_ocr_needed(pdfresponseofconverted.content, producermessage)
        # "Converted PDF , No of pages in {0} is {1} ".format(_filename, len(reader.pages)))
        pagecount = len(reader.pages)
    #else:
        # check to see if non-pdf file need ocr service
        #ocr_needed = False #verify_ocr_needed(response.content, producermessage)

    if reader:
        BytesIO().close()
        reader.stream.close()
    sig = hashlib.sha1()
    for line in response.iter_lines():
        sig.update(line)

    return (sig.hexdigest(), pagecount)


def get_page_properties(original_pdf, pagenum, font="BC-Sans") -> dict:
    """Getting parameters of previous page for new page"""
    width = get_dimension_value(original_pdf.pages[pagenum].mediabox.width)  
    height = get_dimension_value(original_pdf.pages[pagenum].mediabox.height)
    rotation = original_pdf.pages[pagenum].get("/Rotate")
    fontsize=10
    return {
        "width": width,
        "height": height,
        "fontsize": fontsize,
        "font": font,
        "numberofpages": len(original_pdf.pages),
        "rotation":rotation
    }

def get_dimension_value(value):
    return float(value) if isinstance(value, (Decimal, float)) else value

def __converttoPST(creationdate):
    try:
        if not creationdate or not creationdate.startswith("D:"):
            return "Unknown PST"

        timestamp_str = creationdate[2:].replace("'", ":")
        if timestamp_str.endswith(":"):
            timestamp_str = timestamp_str[:-1]

        # Basic year sanity check
        year = int(timestamp_str[:4])
        if year < 1900:
            return "Unknown PST"

        timestamp_utc = maya.parse(timestamp_str).datetime(to_timezone='America/Vancouver', naive=False)
        return timestamp_utc.strftime("%Y/%m/%d %I:%M:%S %p") + " PST"
    
    except Exception as e:
        print(f"[__converttoPST] Failed to parse date '{creationdate}': {e}")
        return "Unknown PST"
    
def verify_ocr_needed(content, message):
    try:
        if (message.incompatible is not None and message.incompatible.lower() == 'true'):
            return False
        with fitz.open(stream=BytesIO(content), filetype="pdf") as doc:
            ocr_required = needs_ocr(doc) or has_fillable_forms(doc)
            return ocr_required
    except Exception as e:
        print(f"Error in ocr validation: {e}")
