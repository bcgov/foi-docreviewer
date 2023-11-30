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
from pypdf.generic import DictionaryObject, ArrayObject, IndirectObject, NameObject, TextStringObject
import fitz
from io import BytesIO
from html import escape
import hashlib
import uuid
from re import sub
from utils import (
    gets3credentialsobject,
    getdedupeproducermessage,
    dedupe_s3_region,
    dedupe_s3_host,
    dedupe_s3_service,
    dedupe_s3_env,
    request_management_api,
    file_conversion_types,
    convert_to_pst
)

# font_path = '../utils/common/BCSans-Regular_2f.ttf'

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

def savedocumenttos3(pdfwithannotations, s3uripath, auth):
    uploadresponse = requests.put(s3uripath, data=pdfwithannotations, auth=auth)
    uploadresponse.raise_for_status()

def extract_annotations_from_pdf(pdf_document):
    all_annotations = []

    for page_num in range(pdf_document.page_count):
        page = pdf_document.load_page(page_num)
        annotations = page.annots()
        for annot in annotations:
            annot_dict = {
                'Name': annot.info.get('name', ''),
                'Content': annot.info.get('content', ''),
                'Title': annot.info.get('title', ''),
                'CreationDate': annot.info.get('creationDate', ''),
                'ModDate': annot.info.get('modDate', ''),
                'Subject': annot.info.get('subject', ''),
                'ID': annot.info.get('id', ''),
                'AssociatedText': '',
                'PageNumber': page_num
            }
            if annot.type[0] in (5, 8) :  # Check if annotation is a highlight(8), text markup(5) (e.g., underline, strikeout)
                text = page.get_text("text", clip=annot.rect)
                annot_dict['AssociatedText'] = text
            all_annotations.append(annot_dict)
    return all_annotations

def __constructannotationtext(annot):
    # Construct annotation text
    creationdate = convert_to_pst(annot['CreationDate']) if annot['CreationDate'] else ''
    moddate = convert_to_pst(annot['ModDate']) if annot['ModDate'] else ''
    annot_text = f"Name: {annot['Name']}\nContent: {annot['Content']}\nTitle: {annot['Title']}\nAssociated Text: {annot['AssociatedText']}"            
    annot_text += f"Creation Date: {creationdate}\nMod Date: {moddate}\n"
    annot_text += f"Subject: {annot['Subject']}\nPage Number: {annot['PageNumber']}\nID: {annot['ID']}\n\n"
    return annot_text

def add_annotations_as_text_to_end_of_pdf(input_pdf, bytes_stream):
    pdf_document = fitz.open(stream=input_pdf)
    output_pdf = fitz.open()

    all_annotations = extract_annotations_from_pdf(pdf_document)
    if len(all_annotations) > 0:
        page_height = 792
        text_line_spacing = 15  # Adjust line spacing as needed
        text_start_position = 50
        pagecount = pdf_document.page_count
        # Add a blank page to start with
        pdf_document.insert_page(pagecount)
        # Variables to track text overflow and page index
        page_index = pagecount

        # Loop through all annotations
        for annot in all_annotations:
            annot_text = __constructannotationtext(annot)
            lines_needed = len(annot_text.split('\n'))
            last_page = pdf_document.load_page(page_index)
            # Check if the text will fit on the current page
            if text_start_position + lines_needed * text_line_spacing > page_height - 50:
                page_index += 1
                # If text won't fit, add a new blank page
                pdf_document.insert_page(page_index)
                # Load the newly added page
                last_page = pdf_document.load_page(page_index)
                text_start_position = 50
            try:
                ## Insert remaining text onto the current page
                # font_name = last_page.insert_font(font_path)
                # last_page.insert_text((50, text_start_position_1), annot_text, fontsize=10, fontname=font_name)#fontname was throwing error for one of the document hence commeting this.
                last_page.insert_text((50, text_start_position), annot_text, fontsize=10) # default font is helv
            except Exception as e:
                print(f"Error occurred while inserting text: {e}")
                
            # Update the vertical position for the next annotation text
            text_start_position += lines_needed * text_line_spacing
        output_pdf.insert_pdf(pdf_document)
        processedpagecount = 1
        if output_pdf:
            processedpagecount = output_pdf.page_count
            output_pdf.save(bytes_stream)
        return processedpagecount

def handleannotationsinpdf(_bytes, filepath, extension, auth):
    try:
        bytes_stream = BytesIO()
        processedpagecount = add_annotations_as_text_to_end_of_pdf(_bytes, bytes_stream)            
        _updatedbytes = bytes_stream.getvalue()
        if len(_updatedbytes) > 0:
            s3uripath = path.splitext(filepath)[0] + "_updated" + extension
            savedocumenttos3(_updatedbytes, s3uripath, auth)
        return processedpagecount, s3uripath
    except Exception as e:
        print(f"Error occurred while processing pdf with annotations: {e}")

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
    processedpagecount = 1
    processedfilepath = ""
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
    if extension.lower() in [".pdf"]:
        _bytes = BytesIO(response.content)
        processedpagecount, processedfilepath = handleannotationsinpdf(_bytes, filepath, extension, auth)
        reader = PdfReader(_bytes)
        pagecount = len(reader.pages)
        attachments = []
        if reader.attachments:
            if "/Collection" in reader.trailer["/Root"]:
                producermessage.attributes["isportfolio"] = True
            else:
                producermessage.attributes["hasattachment"] = True
            for name in reader.attachments:
                s3uripath = (
                    path.splitext(filepath)[0]
                    + "/"
                    + "{0}{1}".format(uuid.uuid4(), path.splitext(name)[1])
                )
                data = b"".join(reader.attachments[name])
                uploadresponse = requests.put(s3uripath, data=data, auth=auth)
                uploadresponse.raise_for_status()
                attachment = {
                    "filename": escape(sub("<[0-9]+>", "", name, 1)),
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

    return (sig.hexdigest(), pagecount, processedpagecount, processedfilepath)
