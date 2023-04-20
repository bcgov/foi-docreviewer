from utils import getdbconnection
from utils.basicutils import to_json
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

def recordjobstart(message):
    conn = getdbconnection()
    try:        
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO public."PDFStitchJob"
            (pdfstitchjobid, version, ministryrequestid, category, inputfiles, outputfiles, status, message, createdby)
            VALUES (%s::integer, %s::integer, %s::integer, %s, %s, %s, %s, %s, %s) on conflict (pdfstitchjobid,version) do nothing returning pdfstitchjobid;''',
            (message.jobid, 2, message.ministryrequestid, message.category.lower(), to_json(message.attributes), None, "started", None, message.createdby))
        conn.commit()
        cursor.close()
    except(Exception) as error:
        logging.error("Error in recordjobstart")
        logging.error(error)
        raise
    finally:
        if conn is not None:
            conn.close()
        

def recordjobend(pdfstitchmessage, error, finalmessage=None, message=""):
    conn = getdbconnection()
    try:
        cursor = conn.cursor()
        outputfiles = finalmessage.finaloutput if finalmessage is not None else None

        cursor.execute('''INSERT INTO public."PDFStitchJob"
            (pdfstitchjobid, version, ministryrequestid, category, inputfiles, outputfiles, status, message, createdby)
            VALUES (%s::integer, %s::integer, %s::integer, %s, %s, %s, %s, %s, %s) on conflict (pdfstitchjobid,version) do nothing returning pdfstitchjobid;''',
            (pdfstitchmessage.jobid, 3, pdfstitchmessage.ministryrequestid, pdfstitchmessage.category.lower(), to_json(pdfstitchmessage.attributes), to_json(outputfiles), 'error' if error else 'completed', message if error else "", pdfstitchmessage.createdby))
        
        conn.commit()
        cursor.close()
    except(Exception) as error:
        logging.error("Error in recordjobend")
        logging.error(error)
        raise
    finally:
        if conn is not None:
            conn.close()
        

def ispdfstichjobcompleted(jobid, category):
    conn = getdbconnection()
    try:        
        cursor = conn.cursor()
        cursor.execute('''(SELECT COUNT(1) FILTER (WHERE status = 'error') AS error,
                        COUNT(1) FILTER (WHERE status = 'completed') AS completed,
                        sq.outputfiles
                            FROM (
                            SELECT MAX(version) AS version, pdfstitchjobid, outputfiles::jsonb
                            FROM public."PDFStitchJob"
                            WHERE pdfstitchjobid = %s::integer and category = %s and outputfiles is not null
                            GROUP BY pdfstitchjobid, outputfiles::jsonb
                            ) sq
                            JOIN public."PDFStitchJob" pdfsj ON pdfsj.pdfstitchjobid = sq.pdfstitchjobid AND pdfsj.version = sq.version
                            GROUP BY sq.outputfiles
                                 )''',(jobid, category))
        
        (joberr, jobcompleted, attributes) = cursor.fetchone()
        
        print("joberr == ", joberr)
        print("jobcompleted == ", jobcompleted)
        print("attributes == ", attributes)
        cursor.close()
        return jobcompleted == 1, joberr == 1, attributes
    except(Exception) as error:
        logging.error("Error in getting the complete job status")
        logging.error(error)
        raise
    finally:
        if conn is not None:
            conn.close()
        