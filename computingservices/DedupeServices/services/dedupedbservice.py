from . import getdbconnection
from models import dedupeproducermessage
import datetime

def savedocumentdetails(dedupeproducermessage, hashcode):
    try:
        conn = getdbconnection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO public."Documents" (version, \
        filename, filepath,foiministryrequestid,createdby,created_at,statusid) VALUES(%s::integer, %s, %s,%s::integer,%s,%s,%s::integer) RETURNING documentid;', (1, dedupeproducermessage.filename, dedupeproducermessage.s3filepath,
        dedupeproducermessage.ministryrequestid,'{"user":"dedupeservice"}',datetime.date.today(),1))
        conn.commit()
        id_of_new_row = cursor.fetchone() 

        cursor.execute('INSERT INTO public."DocumentHashCodes" (documentid, \
        rank1hash,created_at) VALUES(%s::integer, %s,%s)', (id_of_new_row, hashcode,datetime.date.today()))

        conn.commit()

        cursor.close()
        conn.close()
        return True
    except(Exception) as error:
        print(error) 
        return False  
    


