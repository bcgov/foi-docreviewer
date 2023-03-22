from utils import getdbconnection
from utils.basicutils import SetEncoder, to_json
from datetime import datetime
import json


def savefinaldocumentpath(finalpackage, ministryid, category, userid):
    try:
        finalpackagepath = finalpackage.get("documentpath") if finalpackage is not None else ""
        conn = getdbconnection()
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO public."PDFStitchPackageMaster"
            (ministryrequestid, category, finalpackagepath, createdby)
            VALUES (%s::integer, %s, %s, %s) returning pdfstitchpackagemasterid;''',
            (ministryid, category, finalpackagepath, userid))
        conn.commit()
        cursor.close()
        conn.close()
    except(Exception) as error:
        print(error)
        raise
def recordjobstart(message):
    try:
        conn = getdbconnection()
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO public."PDFStitchJob"
            (pdfstitchjobid, version, ministryrequestid, category, inputfiles, outputfiles, status, message, createdby)
            VALUES (%s::integer, %s::integer, %s::integer, %s, %s, %s, %s, %s, %s) returning pdfstitchjobid;''',
            (message.jobid, 2, message.ministryrequestid, message.category, to_json(message.attributes), None, "started", None, message.createdby))
        conn.commit()
        cursor.close()
        conn.close()
    except(Exception) as error:
        print(error)
        raise

def recordjobend(pdfstitchmessage, error, finalmessage=None, message=""):
    try:
        conn = getdbconnection()
        cursor = conn.cursor()
        outputfiles = finalmessage.outputdocumentpath if finalmessage is not None else None

        cursor.execute('''INSERT INTO public."PDFStitchJob"
            (pdfstitchjobid, version, ministryrequestid, category, inputfiles, outputfiles, status, message, createdby)
            VALUES (%s::integer, %s::integer, %s::integer, %s, %s, %s, %s, %s, %s) returning pdfstitchjobid;''',
            (pdfstitchmessage.jobid, 3, pdfstitchmessage.ministryrequestid, pdfstitchmessage.category, to_json(pdfstitchmessage.attributes), to_json(outputfiles), 'error' if error else 'completed', message if error else "", pdfstitchmessage.createdby))
        
        conn.commit()
        cursor.close()
        conn.close()
    except(Exception) as error:
        print(error)
        raise