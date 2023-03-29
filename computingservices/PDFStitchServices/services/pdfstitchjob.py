from utils import getdbconnection
from utils.basicutils import to_json
from datetime import datetime
import json


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
            (message.jobid, 2, message.ministryrequestid, message.category.lower(), to_json(message.attributes), None, "started", None, message.createdby))
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
            (pdfstitchmessage.jobid, 3, pdfstitchmessage.ministryrequestid, pdfstitchmessage.category.lower(), to_json(pdfstitchmessage.attributes), to_json(outputfiles), 'error' if error else 'completed', message if error else "", pdfstitchmessage.createdby))
        
        conn.commit()
        cursor.close()
        conn.close()
    except(Exception) as error:
        print(error)
        raise

def ispdfstichjobcompleted(jobid, category):
    try:
        conn = getdbconnection()
        cursor = conn.cursor()
        cursor.execute('''select count(1)  filter (where status = 'error') as error,
                                 count(1) filter (where status = 'completed') as completed from (
                                 (select max(version) as version,  pdfstitchjobid
                                    from public."PDFStitchJob"
                                    where pdfstitchjobid = %s::integer and category = %s
                                    group by pdfstitchjobid) sq
                                    join public."PDFStitchJob" pdfsj
                                    on pdfsj.pdfstitchjobid = sq.pdfstitchjobid
                                    and pdfsj.version = sq.version
                                 )''',(jobid, category))
        (joberr, jobcompleted) = cursor.fetchone()
        print("joberr == ", joberr)
        print("jobcompleted == ", jobcompleted)
        cursor.close()
        conn.close()
        return jobcompleted == 1, joberr == 1
    except(Exception) as error:
        print(error)
        raise