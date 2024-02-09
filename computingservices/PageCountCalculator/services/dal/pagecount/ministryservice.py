from utils import getfoidbconnection
import logging
from datetime import datetime

class ministryervice:

    @classmethod 
    def getlatestrecordspagecount(cls, ministryrequestid):
        conn = getfoidbconnection()
        try:
            cursor = conn.cursor()
            query = '''
                SELECT recordspagecount
                FROM public."FOIMinistryRequests" 
                WHERE foiministryrequestid = %s::integer AND isactive = true 
                ORDER BY version DESC LIMIT 1;
            '''
            parameters = (ministryrequestid,)
            cursor.execute(query, parameters)
            recordspagecount = cursor.fetchone()[0]
            return recordspagecount
        except Exception as error:
            logging.error("Error in getlatestrecordspagecount")
            logging.error(error)
            raise
        finally:
            if conn is not None:
                conn.close()
    
    @classmethod
    def updaterecordspagecount(cls, ministryrequestid, pagecount, userid):
        conn = getfoidbconnection()
        try:        
            cursor = conn.cursor()
            query = '''
                    UPDATE public."FOIMinistryRequests" SET recordspagecount = %s::integer, updated_at = %s, updatedby = %s
                    WHERE foiministryrequestid = %s::integer AND isactive = true;
                '''
            parameters = (pagecount, datetime.now().isoformat(), userid, ministryrequestid,)
            cursor.execute(query, parameters)
            conn.commit()
            cursor.close()
        except(Exception) as error:
            print("Exception while executing func updaterecordspagecount, Error : {0} ".format(error))
            raise
        finally:
            if conn is not None:
                conn.close()