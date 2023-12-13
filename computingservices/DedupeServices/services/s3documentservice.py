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

def extract_annotations_from_pdf(pdf_document, output_bytestream):
    all_annotations = []
    output_pdf = fitz.open()
    for page_num in range(pdf_document.page_count):
        page = pdf_document.load_page(page_num)
        index = 1
        annotations = page.annots()
        for annot in annotations:

            content = annot.info.get('content', '')
            if content:
                legend_text = f"Legend [{page_num}:{str(index)}]"
                new_content = legend_text + ":The comment text of the annotation is added as part of the pdf."
                index += 1
                author = annot.info.get('title', '')
                # if author:
                new_author = "Original Document Comment"
                annot.set_info(content=new_content,title=new_author)
                annot.update()
                annot_dict = {
                'Legend': legend_text,
                'OriginalContent': content,
                'Author': author,                
                'Subject': annot.info.get('subject', ''),
                'PageNumber': page_num,
                # 'CreationDate': annot.info.get('creationDate', ''),
                # 'ModDate': annot.info.get('modDate', ''),
                # 'Type': annot.type[1]
                }
                all_annotations.append(annot_dict)
            else:
                page.delete_annot(annot)            
    output_pdf.insert_pdf(pdf_document)
    if output_pdf:
        output_pdf.save(output_bytestream)
    return all_annotations


def __constructannotationtext(annot):
    # Construct annotation text
    annot_text = ""
   
    annot_text = __append_if_exists(annot_text, 'Legend', annot["Legend"])
    annot_text = __append_if_exists(annot_text, 'Subject', annot["Subject"])
    annot_text = __append_if_exists(annot_text, 'Author', annot["Author"])
    annot_text = __append_if_exists(annot_text, 'Original Content', annot["OriginalContent"])
    # creationdate = convert_to_pst(annot['CreationDate']) if annot['CreationDate'] else ''
    # moddate = convert_to_pst(annot['ModDate']) if annot['ModDate'] else ''
    # annot_text = __append_if_exists(annot_text, 'Annotation Type', annot["Type"])
    # annot_text = __append_if_exists(annot_text, 'ModifiedContent', annot["ModifiedContent"])
    # annot_text = __append_if_exists(annot_text, 'Creation Date', creationdate)
    # annot_text = __append_if_exists(annot_text, 'Modified Date', moddate)
    annot_text += "\n"
    return annot_text

def add_annotations_as_text_to_pdf(source_document, bytes_stream):
    output_bytestream = BytesIO()
    annotations = extract_annotations_from_pdf(source_document, output_bytestream)
    updated_stream = output_bytestream.getvalue()
    updated_document = fitz.open(stream=updated_stream)
    processedpagecount = 1
    destination_document = fitz.open()
    text_line_spacing = 15
    page_height = 792
    new_page_index = 0
    for page_index in range(updated_document.page_count):
        if new_page_index == 0:
            new_page_index = page_index
        text_start_position = 50
        annotations_on_page = [annot for annot in annotations if annot.get('PageNumber') == page_index]
        for annot in annotations_on_page:
            annot_text = __constructannotationtext(annot)
            lines_needed = len(annot_text.split('\n'))
            print(f'annot_text = {annot_text}')
            if text_start_position == 50:
                new_page_index += 1
                updated_document.insert_page(new_page_index)
                new_page = updated_document.load_page(new_page_index)
            if text_start_position + lines_needed * text_line_spacing > page_height - 50:
                new_page_index += 1
                updated_document.insert_page(new_page_index)
                new_page = updated_document.load_page(new_page_index)
                text_start_position = 50
            try:
                new_page.insert_text((50, text_start_position), annot_text, fontsize=10)
            except Exception as e:
                print(f"Error occurred while inserting text: {e}")
            text_start_position += lines_needed * text_line_spacing
        new_page_index += 1    
    
    destination_document.insert_pdf(updated_document)    

    if destination_document:
        processedpagecount = destination_document.page_count
        destination_document.save(bytes_stream)
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
