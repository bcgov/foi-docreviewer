from io import BytesIO
from zipfile import ZipFile
import zipfile
import tempfile
import logging
from models import zipperproducermessage
from datetime import datetime
from .s3documentservice import (
    gets3documentbytearray,
    uploadbytes,
    getcredentialsbybcgovcode,
)
from .zipperdboperations import recordjobstatus, savefinaldocumentpath
from .notificationservice import notificationservice
import json
import traceback
import PyPDF2

def processmessage(message):
    try:
        s3credentials = getcredentialsbybcgovcode(message.bcgovcode)
        recordjobstatus(
            pdfstitchmessage=message,
            version=3,
            error=None,
            isziping=True,
            status="zippingstarted",
            finalmessage="",
            message="",
        )
        result = __zipfilesandupload(message, s3credentials)
        recordjobstatus(
            pdfstitchmessage=message,
            version=4,
            error=None,
            isziping=True,
            status="zippingcompleted",
            finalmessage="",
            message="",
        )
        if result.get("success"):
            logging.info("final document path = %s", result.get("documentpath"))
            savefinaldocumentpath(
                result, message.ministryrequestid, message.category, message.createdby
            )
            recordjobstatus(
                pdfstitchmessage=message,
                version=5,
                error=None,
                isziping=False,
                status="completed",
                finalmessage="",
                message="",
            )
        else:
            errormessage = "Error in uploading the final document %s", result.get(
                "filename"
            )
            logging.error(errormessage)
            recordjobstatus(
                pdfstitchmessage=message,
                version=5,
                error=None,
                isziping=True,
                status="error",
                finalmessage=message,
                message="Zipfiles upload return an error",
            )
    except Exception as ex:
        logging.error("error in writing the bytearray")
        logging.error(ex)
        recordjobstatus(
            pdfstitchmessage=message,
            version=5,
            error=None,
            isziping=False,
            status="error",
            finalmessage=message,
            message='Error while processing zipper message - ' + str(ex)
        )


def sendnotification(readyfornotification, producermessage):
    if readyfornotification == True and producermessage.category.lower() == "harms":
        notificationservice().sendharmsnotification(producermessage)
    elif readyfornotification == True and producermessage.category.lower() in (
        "redline",
        "responsepackage",
    ):
        notificationservice().sendredlineresponsenotification(producermessage)


def __getdocumentbytearray(file, s3credentials):
    try:
        return gets3documentbytearray(file, s3credentials)
    except Exception as error:
        logging.error(error)
        raise ValueError(file["filename"], error)


def __zipfilesandupload(_message, s3credentials):
    zipped_bytes = None
    try:
        with tempfile.SpooledTemporaryFile() as tp:
            with zipfile.ZipFile(
                tp, "w", zipfile.ZIP_DEFLATED, compresslevel=9, allowZip64=True
            ) as zip:
                _jsonfiles = json.loads(_message.filestozip)
                print("\n_jsonfiles:",_jsonfiles)
                for fileobj in _jsonfiles:
                    filename = fileobj["filename"]
                    print("\nfilename:",filename)
                    
                    _docbytes = __getdocumentbytearray(fileobj, s3credentials)
                    _formattedbytes = None
                    if(filename == "{0}.pdf".format(_message.requestnumber)):
                        try:                           
                            _formattedbytes = __removesensitivecontent(_docbytes)                           
                        except Exception:
                            print(traceback.format_exc())
                    zip.writestr(
                        filename, _docbytes if _formattedbytes is None else _formattedbytes
                    )
                    
            tp.seek(0)           
            zipped_bytes = tp.read()
            if _message.foldername:
                filepath = __getzipfilepath(_message.foldername, _message.requestnumber)
            else:
                filepath = __getzipfilepath(_message.category, _message.requestnumber)
            logging.info("zipfilename = %s", filepath)
            docobj = uploadbytes(
                filepath,
                zipped_bytes,
                _message.requestnumber,
                _message.bcgovcode,
                s3credentials,
            )
            return docobj
    except Exception as ex:
        logging.error("error in writing the bytearray")
        logging.error(ex)
        raise
    finally:
        zipped_bytes = None


def __getzipfilepath(foldername, filename):
    return (
        foldername.capitalize() + "/" + filename + ".zip"
        if foldername is not None
        else filename + ".zip"
    )


def __removesensitivecontent(documentbytes):
    # clear metadata
    reader2 = PyPDF2.PdfReader(BytesIO(documentbytes))
    # Check if metadata exists.
    if reader2.metadata is not None:
        # Create a new PDF file without metadata.
        writer = PyPDF2.PdfWriter()
        # Copy pages from the original PDF to the new PDF.
        for page_num in range(len(reader2.pages)):
            page = reader2.pages[page_num]                
            writer.add_page(page)        
        #writer.remove_links() # to remove comments.
        buffer = BytesIO()
        writer.write(buffer)
        return buffer.getvalue()