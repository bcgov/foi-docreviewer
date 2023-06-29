from utils import getdbconnection
import json
import logging


def savefinaldocumentpath(finalpackage, ministryid, category, userid):
    try:
        finalpackagepath = finalpackage.get("documentpath") if finalpackage is not None else ""
        conn = getdbconnection()
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO public."PDFStitchPackage"
            (ministryrequestid, category, finalpackagepath, createdby)
            VALUES (%s::integer, %s, %s, %s) returning pdfstitchpackageid;''',
            (ministryid, category.lower(), finalpackagepath, userid))
        conn.commit()
        cursor.close()        
    except(Exception) as error:
        logging.error("Error in saving the final output files")
        logging.error(error)
        raise
    finally:
        if conn is not None:
            conn.close()

def recordjobstatus(pdfstitchmessage, version, error,isziping=False, status="",finalmessage=None, message=""):
    conn = getdbconnection()
    print("Inside recordjobend")
    try:
        cursor = conn.cursor()
        outputfiles = pdfstitchmessage.finaloutput if finalmessage is not None else None       
        category = pdfstitchmessage.category.lower() + "-zipper" if isziping else pdfstitchmessage.category.lower()
        status = 'error' if error else status
           
        cursor.execute('''INSERT INTO public."PDFStitchJob"
            (pdfstitchjobid,version, ministryrequestid, category, inputfiles, outputfiles, status, message, createdby)
            VALUES (%s::integer,%s::integer, %s::integer, %s, %s, %s, %s, %s, %s) on conflict (pdfstitchjobid,version) do nothing returning pdfstitchjobid;''',
            (pdfstitchmessage.jobid,version, pdfstitchmessage.ministryrequestid, category.lower(), json.dumps(pdfstitchmessage.attributes), json.dumps(outputfiles), status, message if error else "", pdfstitchmessage.createdby))
        
        conn.commit()
        cursor.close()
    except(Exception) as error:
        logging.error("Error in recordjobend")
        logging.error(error)
        raise
    finally:
        if conn is not None:
            conn.close()