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

def extract_annotations(reader, pagecount):
    annotations = []

    for page_num in range(pagecount):
        page = reader.pages[page_num]
        if '/Annots' in page:
            for annot in page['/Annots']:
                if isinstance(annot, IndirectObject):
                    annotations.append((annot.get_object(), page_num + 1))  # Include page number
    # print("annotations >>>>>>>>>>>>> ", annotations)
    return annotations

def add_annotations_to_pages(input_pdf, annotations):
    writer = PdfWriter()

    for page in input_pdf.pages:
        writer.add_page(page)

    page = writer.add_blank_page()

    # Set initial parameters for pagination
    annotations_per_page = 10  # Number of annotations per page
    # current_page = 0
    remaining_annotations = annotations[:]

    while remaining_annotations:
        # height_offset = len(annotations) * 60  # Initial height offset
        # height_offset = 750
        # print("height_offset = ", height_offset)
        for annot, page_number in remaining_annotations[:annotations_per_page]:
            author = annot.get('/T', 'Unknown Author')
            content = annot.get('/Contents', 'No Annotation')

            annot_text = f"Page Number: {page_number}\nAuthor: {author}\nAnnotation: {content}"
            print("<<<<<<<<< annot_text >>>>>>>>>>")
            print(annot_text)

            annot_text_object = TextStringObject(annot_text)
            print("<<<<<<<<< annot_text_object >>>>>>>>>>")
            print(annot_text_object)
            page.merge_page(annot_text_object)
            # text_annotation = DictionaryObject({
            #     NameObject('/Type'): NameObject('/Annot'),
            #     NameObject('/Subtype'): NameObject('/FreeText'),
            #     NameObject('/Contents'): TextStringObject(annot_text),
            #     NameObject('/Rect'): ArrayObject([50, height_offset, 400, height_offset - 50]),
            #     NameObject('/F'): 4  # Flags for font size, color, etc. (may need adjustments)
            # })
            
            # print("<<<<<<<<< text_annotation >>>>>>>>>>")
            # print(text_annotation)

            # page[NameObject('/Annots')].append(text_annotation)
            # height_offset -= 60  # Adjust this value as needed for spacing

        del remaining_annotations[:annotations_per_page]

        # If there are remaining annotations, add a new page
        if remaining_annotations:
            page = writer.add_page()

    output_stream = BytesIO()
    writer.write(output_stream)
    print("<<<<<<<< writer.write(output_stream) >>>>>>>>>")
    output_stream.seek(0)  # Set the stream position to the beginning
    print("<<<<<<<< output_stream.seek(0) >>>>>>>>>")

    return output_stream.getvalue()

def add_blank_page_with_annotations(input_pdf, annotations):
    writer = PdfWriter()

    for page in input_pdf.pages:
        writer.add_page(page)

    # Add a blank page at the end
    writer.add_blank_page()
    print("<<<<<<<< writer.add_blank_page() >>>>>>>>>")
    # Add extracted annotations to the blank page
    blank_page = writer.pages[-1]
    print("<<<<<<<< writer.pages[-1] >>>>>>>>>")
    # annots_array = ArrayObject()

    # # Add each annotation to the annotations array
    # for annot in annotations:
    #     annots_array.append(annot)
    # print("<<<<<<<<<< annots_array >>>>>>>>>>>>>>")

    # Set initial height for positioning annotations
    height_offset = len(annotations) * 60

    # Start writing annotations as text on the blank page
    for annot in annotations:
        author = annot.get('/T', 'Unknown Author')
        content = annot.get('/Contents', 'No Annotation')

        annot_text = f"Author: {author}\nAnnotation: {content}"
        print("<<<<<<<<< annot_text >>>>>>>>>>")
        print(annot_text)

        text_annotation = DictionaryObject({
            NameObject('/Type'): NameObject('/Annot'),
            NameObject('/Subtype'): NameObject('/FreeText'),
            NameObject('/Contents'): TextStringObject(annot_text),
            NameObject('/Rect'): ArrayObject([50, height_offset, 400, height_offset - 50]),
            NameObject('/F'): 4  # Flags for font size, color, etc. (may need adjustments)
        })

        print("<<<<<<<<< text_annotation >>>>>>>>>>")
        print(text_annotation)

        # Add each text annotation to the blank page
        blank_page[NameObject('/Annots')].append(text_annotation)

        # Adjust the height offset for the next annotation
        height_offset -= 60  # Adjust this value as needed for spacing
        
        blank_page[NameObject('/Annots')].append(text_annotation)
    
    # blank_page[DictionaryObject("/Annots")] = annotations
    print("<<<<<<<< blank_page[DictionaryObject()] >>>>>>>>>")

    output_stream = BytesIO()
    writer.write(output_stream)
    print("<<<<<<<< writer.write(output_stream) >>>>>>>>>")
    output_stream.seek(0)  # Set the stream position to the beginning
    print("<<<<<<<< output_stream.seek(0) >>>>>>>>>")

    return output_stream.getvalue()
def savedocumenttos3(pdfwithannotations, s3uri, extension, auth):
    s3uripath = s3uri + "_updated" + extension
    uploadresponse = requests.put(s3uripath, data=pdfwithannotations, auth=auth)
    uploadresponse.raise_for_status()


def modify_annotations_show_in_balloons(input_pdf, bytes_stream):
    pdf_document = fitz.open(stream=input_pdf)
    output_pdf = fitz.open()
    for page_num in range(pdf_document.page_count):
        page = pdf_document.load_page(page_num)
        annotations = page.annots()

        for annot in annotations:
            print("<<<<<<<<<<< inside for loop >>>>>>>>>>>")            
            print(annot.info.get('ShowInBalloons'))
            print(annot.info)
            # Check if the annotation has 'ShowInBalloons' property
            if annot.info.get('ShowInBalloons') is not None:
                print("<<<<<<<<<<<< inside if >>>>>>>>>>>>>>")
                annot.set_info(info='ShowInBalloons', string='true')  # Set ShowInBalloons property
                print("<<<<<<<<<<<< set_info if >>>>>>>>>>>>>>")
    
    output_pdf.insert_pdf(pdf_document)
    ## pdf_document.save(output_pdf)
    # pdf_document.close()
    # input_pdf.close()
    # del pdf_document
    # del input_pdf
    if output_pdf:
        output_pdf.save(bytes_stream)
        # output_pdf.close()
        # fitz.TOOLS.store_shrink(100)
        # del output_pdf

def extract_annotations_from_pdf(pdf_document):
    all_annotations = []

    for page_num in range(pdf_document.page_count):
        page = pdf_document.load_page(page_num)
        annotations = page.annots()
        # print(annotations)
        for annot in annotations:
            print(annot.info)
            annot_dict = {
                'Name': annot.info.get('name', ''),
                'Content': annot.info.get('content', ''),
                'Title': annot.info.get('title', ''),
                'CreationDate': annot.info.get('creationDate', ''),
                'ModDate': annot.info.get('modDate', ''),
                'Subject': annot.info.get('subject', ''),
                'ID': annot.info.get('id', ''),
            }
            all_annotations.append(annot_dict)
    return all_annotations

# def add_annotations_as_text_to_end_of_pdf(input_pdf, bytes_stream):
#     pdf_document = fitz.open(stream=input_pdf)
#     output_pdf = fitz.open()

#     all_annotations = extract_annotations_from_pdf(pdf_document)
#     # print("<<<<<<<<<< all_annotations >>>>>>>>>>>")
#     # print(all_annotations)
#     # Constants for page dimensions (adjust as needed)
#     page_width = 612
#     page_height = 792
#     text_start_position = page_height - 50
#     text_line_spacing = 15  # Adjust line spacing as needed
#     max_lines_per_page = 40  # Adjust this value to fit the text properly
#     pagecount = pdf_document.page_count
#     print("pagecount ===== ", pagecount)
#     # Add a blank page to start with
#     pdf_document.insert_page(pagecount)
#     print("<<<<<<<<<< pdf_document.insert_page >>>>>>>>>>>>>")
#     # Variables to track text overflow and page index
#     overflow = False
#     remaining_text = ""
#     page_index = pagecount + 1

#     # Loop through all annotations
#     for annot in all_annotations:
#         # Construct annotation text
#         annot_text = f"Name: {annot['Name']}\nContent: {annot['Content']}\nTitle: {annot['Title']}\n"
#         annot_text += f"Creation Date: {annot['CreationDate']}\nMod Date: {annot['ModDate']}\n"
#         annot_text += f"Subject: {annot['Subject']}\nID: {annot['ID']}\n\n"

#         lines_needed = len(annot_text.split('\n'))
#         last_page = pdf_document.load_page(page_index)
#         # Check if the text will fit on the current page
#         if lines_needed <= max_lines_per_page:            
#             remaining_text += annot_text
#             print("remaining_text === ", remaining_text)
#         else:
#             print("<<<<< inside else >>>>>>>>>>")
#             # If text won't fit, add a new blank page
#             pdf_document.insert_page(pdf_document.page_count)
#             print("<<<<< inside else pdf_document.insert_page >>>>>>>>>>")
#             page_index += 1

#             # Load the newly added page
#             last_page = pdf_document.load_page(page_index)
#             print("<<<<< pdf_document.load_page >>>>>>>>>>")
#             remaining_text = annot_text
#             print("inside else remaining_text === ", remaining_text)

#         # Insert remaining text onto the current page
#         print("before insert remaining_text === ", remaining_text)
#         last_page.insert_text((50, page_height - 50), remaining_text, fontsize=10)
#         print("<<<<< last_page.insert_text >>>>>>>>>>")
    
#     output_pdf.insert_pdf(pdf_document)
#     print("<<<<< output_pdf.insert_pdf >>>>>>>>>>")
    
#     # pdf_document.save(output_pdf)
#     # pdf_document.close()
#     if output_pdf:
#         output_pdf.save(bytes_stream)

def add_annotations_as_text_to_end_of_pdf(input_pdf, bytes_stream):
    pdf_document = fitz.open(stream=input_pdf)
    output_pdf = fitz.open()

    all_annotations = extract_annotations_from_pdf(pdf_document)
    if len(all_annotations) > 0:
        page_height = 792
        text_line_spacing = 15  # Adjust line spacing as needed
        annotations_per_page = 5
        text_start_position = page_height - 50
        text_start_position_1 = 50
        # text_start_positions = [page_height - (50 + (annotations_per_page - 1) * text_line_spacing * i)
        #                         for i in range(1, len(all_annotations) // annotations_per_page + 2)]
        # print(text_start_positions)
        pagecount = pdf_document.page_count
        print("pagecount ===== ", pagecount)
        # Add a blank page to start with
        pdf_document.insert_page(pagecount)
        print("<<<<<<<<<< pdf_document.insert_page >>>>>>>>>>>>>")
        # Variables to track text overflow and page index
        page_index = pagecount

        # Loop through all annotations
        for annot in all_annotations:
            # Construct annotation text
            # print(annot)
            creationdate = convert_to_pst(annot['CreationDate']) if annot['CreationDate'] else ''
            moddate = convert_to_pst(annot['ModDate']) if annot['ModDate'] else ''
            annot_text = f"Name: {annot['Name']}\nContent: {annot['Content']}\nTitle: {annot['Title']}\n"
            annot_text += f"Creation Date: {creationdate}\nMod Date: {moddate}\n"
            annot_text += f"Subject: {annot['Subject']}\nID: {annot['ID']}\n\n"

            lines_needed = len(annot_text.split('\n'))
            # print("lines_needed == ", lines_needed)
            last_page = pdf_document.load_page(page_index)
            # print("if condition == ", text_start_position - lines_needed * text_line_spacing)
            print("if condition == ", text_start_position_1 + lines_needed * text_line_spacing)
            # Check if the text will fit on the current page
            # if text_start_position - lines_needed * text_line_spacing < 0:
            if text_start_position_1 + lines_needed * text_line_spacing > page_height - 50:
                page_index += 1
                # If text won't fit, add a new blank page
                pdf_document.insert_page(page_index)
                # page_index += 1

                # Load the newly added page
                last_page = pdf_document.load_page(page_index)
                # page_index += 1 # some improvement
                
                text_start_position = page_height - 50
                text_start_position_1 = 50

            # Insert remaining text onto the current page
            print("text_start_position == ", text_start_position)
            print("text_start_position_1 == ", text_start_position_1)
            # print("before insert_text annot_text === ", annot_text)        
            last_page.insert_text((50, text_start_position_1), annot_text, fontsize=10)
            # Update the vertical position for the next annotation text
            text_start_position -= lines_needed * text_line_spacing
            text_start_position_1 += lines_needed * text_line_spacing
            
        
        output_pdf.insert_pdf(pdf_document)
        print("<<<<< output_pdf.insert_pdf >>>>>>>>>>")    

        if output_pdf:
            output_pdf.save(bytes_stream)


def gets3documenthashcode(producermessage):
    s3credentials = __getcredentialsbybcgovcode(producermessage.bcgovcode)
    pagecount = 1
    s3_access_key_id = s3credentials.s3accesskey
    s3_secret_access_key = s3credentials.s3secretkey

    auth = AWSRequestsAuth(
        aws_access_key=s3_access_key_id,
        aws_secret_access_key=s3_secret_access_key,
        aws_host=dedupe_s3_host,
        aws_region=dedupe_s3_region,
        aws_service=dedupe_s3_service,
    )
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
        bytes_stream = BytesIO()
        # modify_annotations_show_in_balloons(_bytes, bytes_stream)
        add_annotations_as_text_to_end_of_pdf(_bytes, bytes_stream)
        reader = PdfReader(_bytes)
        # "No of pages in {0} is {1} ".format(_filename, len(reader.pages)))
        pagecount = len(reader.pages)
        # annotations = extract_annotations(reader, pagecount)
        # pdfwithannotations = add_annotations_to_pages(reader, annotations)
        _updatedbytes = bytes_stream.getvalue()
        print("len ==== ",len(_updatedbytes))
        if len(_updatedbytes) > 0:
            savedocumenttos3(_updatedbytes, path.splitext(filepath)[0], extension.lower(), auth)
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

    return (sig.hexdigest(), pagecount)
