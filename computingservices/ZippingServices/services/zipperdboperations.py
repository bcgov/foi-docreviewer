from utils import getdbconnection
import json
import logging


def savefinaldocumentpath(finalpackage, ministryid, category, userid):
    try:
        finalpackagepath = (
            finalpackage.get("documentpath") if finalpackage is not None else ""
        )
        conn = getdbconnection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO public."PDFStitchPackage"
            (ministryrequestid, category, finalpackagepath, createdby)
            VALUES (%s::integer, %s, %s, %s) returning pdfstitchpackageid;""",
            (ministryid, category.lower(), finalpackagepath, userid),
        )
        conn.commit()
        cursor.close()
    except Exception as error:
        logging.error("Error in saving the final output files")
        logging.error(error)
        raise
    finally:
        if conn is not None:
            conn.close()


def recordjobstatus(
    pdfstitchmessage,
    version,
    error,
    isziping=False,
    status="",
    finalmessage=None,
    message="",
):
    conn = getdbconnection()
    print("Inside recordjobend")
    try:
        cursor = conn.cursor()
        outputfiles = pdfstitchmessage.finaloutput if finalmessage is not None else None
        category = (
            pdfstitchmessage.category.lower() + "-zipper"
            if isziping
            else pdfstitchmessage.category.lower()
        )
        status = "error" if error else status

        cursor.execute(
            """INSERT INTO public."PDFStitchJob"
            (pdfstitchjobid,version, ministryrequestid, category, inputfiles, outputfiles, status, message, createdby)
            VALUES (%s::integer,%s::integer, %s::integer, %s, %s, %s, %s, %s, %s) on conflict (pdfstitchjobid,version) do nothing returning pdfstitchjobid;""",
            (
                pdfstitchmessage.jobid,
                version,
                pdfstitchmessage.ministryrequestid,
                category.lower(),
                json.dumps(pdfstitchmessage.attributes),
                json.dumps(outputfiles),
                status,
                message if error else "",
                pdfstitchmessage.createdby,
            ),
        )

        conn.commit()
        cursor.close()
    except Exception as error:
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
        cursor.execute(
            """(SELECT COUNT(1) FILTER (WHERE status = 'error') AS error,
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
                                 )""",
            (jobid, category),
        )

        result = cursor.fetchone()
        cursor.close()
        if result is not None:
            (joberr, jobcompleted, attributes) = result
            return jobcompleted == 1, joberr == 1, attributes
        return False, False, None

    except Exception as error:
        logging.error("Error in getting the complete job status")
        logging.error(error)
        raise
    finally:
        if conn is not None:
            conn.close()


def isredlineresponsezipjobcompleted(jobid, category):
    conn = getdbconnection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """(SELECT COUNT(1) FILTER (WHERE status = 'error') AS error,
                        COUNT(1) FILTER (WHERE status = 'completed') AS completed
                            FROM (
                            SELECT MAX(version) AS version, pdfstitchjobid
                            FROM public."PDFStitchJob"
                            WHERE pdfstitchjobid = %s::integer and category = %s
                            GROUP BY pdfstitchjobid
                            ) sq
                            JOIN public."PDFStitchJob" pdfsj ON pdfsj.pdfstitchjobid = sq.pdfstitchjobid AND pdfsj.version = sq.version
                                 )""",
            (jobid, category),
        )

        result = cursor.fetchone()
        cursor.close()
        if result is not None:
            (joberr, jobcompleted) = result
            return jobcompleted == 1, joberr == 1
        return False, False

    except Exception as error:
        logging.error("Error in getting the complete job status")
        logging.error(error)
        raise
    finally:
        if conn is not None:
            conn.close()
