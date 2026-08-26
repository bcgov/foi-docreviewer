from . import getdbconnection
from models import dedupeproducermessage
from utils.basicutils import to_json
from utils.loggingutils import log_context, log_event
from utils.foidedupeconfig import compression_workload
from datetime import datetime
import json
import logging


logger = logging.getLogger(__name__)

def savedocumentdetails(dedupeproducermessage, hashcode, pagecount = 1):
    conn = getdbconnection()
    context = log_context(dedupeproducermessage, operation="save_document_details")
    try:        
        cursor = conn.cursor()
        _incompatible = True if str(dedupeproducermessage.incompatible).lower() == 'true' else False

        cursor.execute('INSERT INTO public."Documents" (version, \
        filename, documentmasterid,foiministryrequestid,createdby,created_at,statusid,incompatible, originalpagecount, pagecount) VALUES(%s::integer, %s, %s,%s::integer,%s,%s,%s::integer,%s::bool,%s::integer,%s::integer) RETURNING documentid;',
        (1, dedupeproducermessage.filename, dedupeproducermessage.outputdocumentmasterid or dedupeproducermessage.documentmasterid,
        dedupeproducermessage.ministryrequestid,'{"user":"dedupeservice"}',datetime.now(),1,_incompatible,pagecount,pagecount))
        conn.commit()
        id_of_new_row = cursor.fetchone()

        if (dedupeproducermessage.attributes.get('isattachment', False) and dedupeproducermessage.trigger == 'recordreplace'):
            documentmasterid = dedupeproducermessage.originaldocumentmasterid or dedupeproducermessage.documentmasterid
        else:
            documentmasterid = dedupeproducermessage.documentmasterid

        cursor.execute('''UPDATE public."DocumentAttributes" SET attributes = %s WHERE documentmasterid = %s''',
          (json.dumps(dedupeproducermessage.attributes), documentmasterid))
        conn.commit()

        cursor.execute('INSERT INTO public."DocumentHashCodes" (documentid, \
        rank1hash,created_at) VALUES(%s::integer, %s,%s)', (id_of_new_row, hashcode,datetime.now()))
        conn.commit()

        cursor.close()
        log_event(logger, logging.INFO, "database_recorded", context=context, stage="write")
        return id_of_new_row[0], True
    except(Exception) as error:
        log_event(logger, logging.ERROR, "database_operation_failed", context=context, stage="write", exc_info=True)
        raise
    finally:
        if conn is not None:
            conn.close()

def recordjobstart(dedupeproducermessage):
    conn = getdbconnection()
    context = log_context(dedupeproducermessage, operation="record_job_start", job_version=2)
    try:
        if __doesjobversionexists(dedupeproducermessage.jobid, 2) == False:        
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO public."DeduplicationJob"
                (deduplicationjobid, version, ministryrequestid, batch, type, trigger, documentmasterid, filename, status)
                VALUES (%s::integer, %s::integer, %s::integer, %s, %s, %s, %s, %s, %s) on conflict (deduplicationjobid, version) do nothing returning deduplicationjobid;''',
                (dedupeproducermessage.jobid, 2, dedupeproducermessage.ministryrequestid, dedupeproducermessage.batch, 'rank1', dedupeproducermessage.trigger, dedupeproducermessage.documentmasterid, dedupeproducermessage.filename, 'started'))
            conn.commit()
            cursor.close()
            log_event(logger, logging.INFO, "database_recorded", context=context, stage="write")
        else:
            log_event(logger, logging.WARNING, "duplicate_job", context=context, stage="write")
    except(Exception) as error:
        log_event(logger, logging.ERROR, "database_operation_failed", context=context, stage="write", exc_info=True)
        raise
    finally:
        if conn is not None:
            conn.close()

def recordjobend(dedupeproducermessage, error, message=""):
    conn = getdbconnection()
    context = log_context(dedupeproducermessage, operation="record_job_end", job_version=3)
    try: 
        if __doesjobversionexists(dedupeproducermessage.jobid, 3) == False:
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO public."DeduplicationJob"
                (deduplicationjobid, version, ministryrequestid, batch, type, trigger, documentmasterid, filename, status, message)
                VALUES (%s::integer, %s::integer, %s::integer, %s, %s, %s, %s, %s, %s, %s) on conflict (deduplicationjobid, version) do nothing returning deduplicationjobid;''',
                (dedupeproducermessage.jobid, 3, dedupeproducermessage.ministryrequestid, dedupeproducermessage.batch, 'rank1', dedupeproducermessage.trigger, dedupeproducermessage.documentmasterid, dedupeproducermessage.filename,
                'error' if error else 'completed', message if error else ""))
            conn.commit()
            cursor.close()
            log_event(logger, logging.INFO, "database_recorded", context=context, stage="write")
        else:
            log_event(logger, logging.WARNING, "duplicate_job", context=context, stage="write")
    except(Exception) as error:
        log_event(logger, logging.ERROR, "database_operation_failed", context=context, stage="write", exc_info=True)
        raise
    finally:
        if conn is not None:
            conn.close()

def __doesjobversionexists(jobid, version):
    conn = getdbconnection()
    context = log_context(job_id=jobid, job_version=version, operation="job_version_exists")
    result = 0
    try:
        cursor = conn.cursor()
        cursor.execute('''SELECT count(deduplicationjobid) FROM public."DeduplicationJob"  where deduplicationjobid = %s::integer and version = %s::integer''',(jobid, version))        
        count = cursor.fetchone()[0] 
        result = count             
        cursor.close()
       
    except(Exception) as error:
        log_event(logger, logging.ERROR, "database_operation_failed", context=context, stage="read", exc_info=True)
        raise
    finally:
        if conn is not None:
            conn.close()
    return False if result == 0 else True    

def updateredactionstatus(dedupeproducermessage):
    conn = getdbconnection()
    context = log_context(dedupeproducermessage, operation="update_redaction_status")
    try:        
        cursor = conn.cursor()
        cursor.execute('''update "DocumentMaster" dm
                        set isredactionready = true, updatedby  = 'dedupeservice', updated_at = now()
                        from(
                        select distinct on (documentmasterid) documentmasterid, version, status
                        from  "DeduplicationJob"
                        where ministryrequestid= %s::integer 
                        order by documentmasterid, version desc) as sq
                        where dm.documentmasterid = sq.documentmasterid 
                        and isredactionready = false and sq.status = 'completed' and ministryrequestid = %s::integer''',
            (dedupeproducermessage.ministryrequestid,dedupeproducermessage.ministryrequestid))
        conn.commit()
        cursor.close()
        log_event(logger, logging.INFO, "database_recorded", context=context, stage="write")
    except(Exception) as error:
        log_event(logger, logging.ERROR, "database_operation_failed", context=context, stage="write", exc_info=True)
        raise
    finally:
        if conn is not None:
            conn.close()

def isbatchcompleted(batch):
    conn = getdbconnection()
    context = log_context(batch=batch, operation="batch_completed")
    try:        
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
        return dedupeinprogress == 0 and conversioninprogress == 0, dedupeerr+conversionerr > 0
    except(Exception) as error:
        log_event(logger, logging.ERROR, "database_operation_failed", context=context, stage="read", exc_info=True)
        raise
    finally:
        if conn is not None:
            conn.close()


def pagecalculatorjobstart(message):
        conn = getdbconnection()
        context = log_context(message, operation="page_calculator_job_start")
        try:
                    
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO public."PageCalculatorJob"
                (version, ministryrequestid, inputmessage, status, createdby)
                VALUES (%s::integer, %s::integer, %s, %s, %s) returning pagecalculatorjobid;''',
                (1, message.ministryrequestid, to_json(message), 'pushedtostream', 'dedupeservice'))
            pagecalculatorjobid = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
            log_event(logger, logging.INFO, "database_recorded", context=context, stage="write")
            return pagecalculatorjobid
        except(Exception) as error:
            log_event(logger, logging.ERROR, "database_operation_failed", context=context, stage="write", exc_info=True)
            raise
        finally:
            if conn is not None:
                conn.close()


def compressionjobstart(message):
        conn = getdbconnection()
        context = log_context(message, operation="compression_job_start")
        try:
                    
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO public."CompressionJob"
                (version, ministryrequestid, batch, trigger, filename, status, documentmasterid, workload)
                VALUES (%s::integer, %s::integer, %s, %s, %s, %s, %s, %s) returning compressionjobid;''',
                (1, message.ministryrequestid, message.batch, 'recordupload', message.filename, 'pushedtostream', message.documentmasterid, compression_workload))
            compressionjobid = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
            log_event(logger, logging.INFO, "database_recorded", context=context, stage="write")
            return compressionjobid
        except(Exception) as error:
            log_event(logger, logging.ERROR, "database_operation_failed", context=context, stage="write", exc_info=True)
            raise
        finally:
            if conn is not None:
                conn.close()
