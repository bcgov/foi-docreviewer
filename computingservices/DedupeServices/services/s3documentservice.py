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
from re import sub
import fitz
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
