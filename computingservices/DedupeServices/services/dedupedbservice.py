from . import getdbconnection
from models import dedupeproducermessage
from datetime import datetime
import json

def savedocumentdetails(dedupeproducermessage, hashcode,pagecount = 1 ):
    try:
        conn = getdbconnection()
        cursor = conn.cursor()
               
        _incompatible = True if str(dedupeproducermessage.incompatible).lower() == 'true' else False
        
        cursor.execute('INSERT INTO public."Documents" (version, \
        filename, documentmasterid,foiministryrequestid,createdby,created_at,statusid,incompatible,pagecount) VALUES(%s::integer, %s, %s,%s::integer,%s,%s,%s::integer,%s::bool,%s::integer) RETURNING documentid;',
        (1, dedupeproducermessage.filename, dedupeproducermessage.outputdocumentmasterid or dedupeproducermessage.documentmasterid,
        dedupeproducermessage.ministryrequestid,'{"user":"dedupeservice"}',datetime.now(),1,_incompatible,pagecount))
        conn.commit()
        id_of_new_row = cursor.fetchone()

        cursor.execute('INSERT INTO public."DocumentHashCodes" (documentid, \
        rank1hash,created_at) VALUES(%s::integer, %s,%s)', (id_of_new_row, hashcode,datetime.now()))
        conn.commit()

        cursor.close()
        conn.close()
        return True
    except(Exception) as error:
        print(error)
        raise

def recordjobstart(dedupeproducermessage):
    try:
        conn = getdbconnection()
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO public."DeduplicationJob"
            (deduplicationjobid, version, ministryrequestid, batch, type, trigger, documentmasterid, filename, status)
            VALUES (%s::integer, %s::integer, %s::integer, %s, %s, %s, %s, %s, %s) returning deduplicationjobid;''',
            (dedupeproducermessage.jobid, 2, dedupeproducermessage.ministryrequestid, dedupeproducermessage.batch, 'rank1', dedupeproducermessage.trigger, dedupeproducermessage.documentmasterid, dedupeproducermessage.filename, 'started'))
        conn.commit()
        cursor.close()
        conn.close()
    except(Exception) as error:
        print(error)
        raise

def recordjobend(dedupeproducermessage, error, message=""):
    try:
        conn = getdbconnection()
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO public."DeduplicationJob"
            (deduplicationjobid, version, ministryrequestid, batch, type, trigger, documentmasterid, filename, status, message)
            VALUES (%s::integer, %s::integer, %s::integer, %s, %s, %s, %s, %s, %s, %s) returning deduplicationjobid;''',
            (dedupeproducermessage.jobid, 3, dedupeproducermessage.ministryrequestid, dedupeproducermessage.batch, 'rank1', dedupeproducermessage.trigger, dedupeproducermessage.documentmasterid, dedupeproducermessage.filename,
            'error' if error else 'completed', message if error else ""))
        conn.commit()
        cursor.close()
        conn.close()
    except(Exception) as error:
        print(error)
        raise

def isbatchcompleted(batch):
    try:
        conn = getdbconnection()
        cursor = conn.cursor()
        cursor.execute('''select count(1) filter (where status = 'pushedtostream' or status = 'started') as inprogress,
            count(1) filter (where status = 'error') as error,
            count(1) filter (where status = 'completed') as completed
            from (select max(version) as version,  fileconversionjobid
            from public."FileConversionJob"
            where batch = %s
            group by fileconversionjobid) sq
            join public."FileConversionJob" fcj
                on fcj.fileconversionjobid = sq.fileconversionjobid
                and fcj.version = sq.version;''',
            (batch,)
        )
        (conversioninprogress, conversionerr, _conversioncompleted) = cursor.fetchone()
        if conversioninprogress > 0:
            cursor.close()
            conn.close()
            return False, conversionerr > 0
        cursor.execute('''select count(1) filter (where status = 'pushedtostream' or status = 'started') as inprogress,
            count(1) filter (where status = 'error') as error,
            count(1) filter (where status = 'completed') as completed
            from (select max(version) as version,  deduplicationjobid
            from public."DeduplicationJob"
            where batch = %s
            group by deduplicationjobid) sq
            join public."DeduplicationJob" dj
                on dj.deduplicationjobid = sq.deduplicationjobid
                and dj.version = sq.version;''',
            (batch,)
        )
        (dedupeinprogress, dedupeerr, _dedupecompleted) = cursor.fetchone()
        cursor.close()
        conn.close()
        return dedupeinprogress == 0 and conversioninprogress == 0, dedupeerr+conversionerr > 0
    except(Exception) as error:
        print(error)
        raise




