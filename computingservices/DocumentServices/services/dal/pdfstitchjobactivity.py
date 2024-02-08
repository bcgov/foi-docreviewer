from utils import getdbconnection
import logging
import json

class pdfstitchjobactivity:

    @classmethod
    def recordjobstatus(cls,message,version,status,error=None,errormessage=None):
        category = message.category.lower() + "-summary"
        conn = getdbconnection()
        print("Inside %s recordjobstatus", category)
        try:
            cursor = conn.cursor()
            status = "error" if error else status

            cursor.execute(
                """INSERT INTO public."PDFStitchJob"
                (pdfstitchjobid,version, ministryrequestid, category, inputfiles, status, message, createdby)
                VALUES (%s::integer,%s::integer, %s::integer, %s, %s, %s,  %s, %s) on conflict (pdfstitchjobid,version) do nothing returning pdfstitchjobid;""",
                (
                    message.jobid,
                    version,
                    message.ministryrequestid,
                    category,
                    json.dumps(message.attributes),
                    status,
                    errormessage if error else None,
                    message.createdby,
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