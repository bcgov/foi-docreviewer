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

def __append_if_exists(text, key, value):
    if value:
        text += f"{key}: {value}\n"
    return text

def __construct_annotation_text(annot, page):
    annot_text = ""

    # Extract required fields
    name = annot.info.get('name')
    content = annot.info.get('content')
    title = annot.info.get('title')
    subject = annot.info.get('subject')
    creationdate = annot.info.get('creationDate', '')
    creationdate = convert_to_pst(creationdate) if creationdate else ''
    moddate = annot.info.get('modDate', '')
    moddate = convert_to_pst(moddate) if moddate else ''

    associatedtext = ""
    # Check if annotation is a square(4), circle(5), polygon(6),  highlight(8), 
    # underline(9), strikeOut(11), caret(14), ink/pencil draw(15)
    if annot.type[0] in (4, 5, 6, 8, 9, 11, 14, 15) :  
        text = page.get_text("text", clip=annot.rect)
        associatedtext = text

    annot_text = __append_if_exists(annot_text, 'Annotation Type', annot.type[1])
    annot_text = __append_if_exists(annot_text, 'Name', name)    
    annot_text = __append_if_exists(annot_text, 'Content', content)
    annot_text = __append_if_exists(annot_text, 'Title', title)
    annot_text = __append_if_exists(annot_text, 'Subject', subject)
    annot_text = __append_if_exists(annot_text, 'Creation Date', creationdate)
    annot_text = __append_if_exists(annot_text, 'Modified Date', moddate)
    annot_text = __append_if_exists(annot_text, 'Associated Text', associatedtext)
    annot_text += "\n"
    return annot_text

def add_annotations_as_text_to_pdf(source_document, bytes_stream):
    processedpagecount = 1
    destination_document = fitz.open()
    text_line_spacing = 15
    new_page_index = 0
    for page_index in range(source_document.page_count):
        if new_page_index == 0:
            new_page_index = page_index
        text_start_position = 50
        source_page = source_document.load_page(page_index)        
        page_rotation = source_page.rotation
        source_page.set_rotation(0)
        source_width = source_page.rect.width
        source_height = source_page.rect.height
        new_page = destination_document.new_page(new_page_index,width=source_width, height=source_height)
        new_page.show_pdf_page(new_page.rect, source_document, page_index)
        new_page.set_rotation(page_rotation)
        annotations = source_page.annots()
            
        for annot in annotations:
            annot_text = __construct_annotation_text(annot, source_page)
            lines_needed = len(annot_text.split('\n'))
                
            if text_start_position == 50:
                new_page_index += 1
                new_page = destination_document.new_page(new_page_index,width=source_width, height=source_height)

            if text_start_position + lines_needed * text_line_spacing > source_height - 50:
                new_page_index += 1
                new_page = destination_document.new_page(new_page_index,width=source_width, height=source_height)
                text_start_position = 50
            try:
                new_page.insert_text((50, text_start_position), annot_text, fontsize=10)
            except Exception as e:
                print(f"Error occurred while inserting text: {e}")
            text_start_position += lines_needed * text_line_spacing
        new_page_index += 1    
    
    processedpagecount = destination_document.page_count
    destination_document.save(bytes_stream)

    if destination_document:
        destination_document.close()
        del destination_document
    return processedpagecount

def handleannotationsinpdf(_bytes, filepath, extension, auth):
    try:
        bytes_stream = BytesIO()
        s3uripath = ""
        source_document = fitz.open(stream=_bytes)
        processedpagecount = 1
        has_annots = source_document.has_annots()
        if has_annots:
            processedpagecount = add_annotations_as_text_to_pdf(source_document, bytes_stream)
        _updatedbytes = bytes_stream.getvalue()
        if source_document:
            source_document.close()
        if len(_updatedbytes) > 0:
            # new filename with existing guid filename_updated
            s3uripath = path.splitext(filepath)[0] + "_updated" + extension
            savedocumenttos3(_updatedbytes, s3uripath, auth)
        if bytes_stream:
            bytes_stream.close()
            del bytes_stream
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
