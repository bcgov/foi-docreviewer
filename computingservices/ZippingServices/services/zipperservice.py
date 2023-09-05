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
            message=traceback.format_exc(),
        )
        raise


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
                for fileobj in _jsonfiles:
                    filename = fileobj["filename"]
                    zip.writestr(
                        filename, __getdocumentbytearray(fileobj, s3credentials)
                    )
            tp.seek(0)
            zipped_bytes = tp.read()

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


def __getzipfilepath(category, filename):
    return (
        category.capitalize() + "/" + filename + ".zip"
        if category is not None
        else filename + ".zip"
    )
