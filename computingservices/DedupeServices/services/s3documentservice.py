from . import getdbconnection,gets3credentialsobject
from . import foidedupehashcalulator
from psycopg2 import sql
from os import path
import json
import psycopg2
import requests
from aws_requests_auth.aws_auth import AWSRequestsAuth
from pypdf import PdfReader, PdfWriter
from io import BytesIO
import hashlib
from utils import gets3credentialsobject,getdedupeproducermessage, dedupe_s3_region,dedupe_s3_host,dedupe_s3_service,dedupe_s3_env

def __getcredentialsbybcgovcode(bcgovcode):
    _conn = getdbconnection()
    s3cred = None
    try:                              
        cur = _conn.cursor()
        _sql = sql.SQL("SELECT  attributes FROM {0} WHERE bucket='{1}'and category='Records'".format('public."DocumentPathMapper"','{0}-{1}-e'.format(bcgovcode.lower(),dedupe_s3_env.lower())))
        cur.execute(_sql)
        attributes = cur.fetchone()
        if attributes is not None:
            s3cred = gets3credentialsobject(str(attributes[0]))
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if _conn is not None:
            _conn.close()
            print('Database connection closed.') 

    return s3cred


def gets3documenthashcode(producermessage): 
    
    s3credentials = __getcredentialsbybcgovcode(producermessage.bcgovcode)
    pagecount = 1
    s3_access_key_id= s3credentials.s3accesskey
    s3_secret_access_key= s3credentials.s3secretkey
        
    auth = AWSRequestsAuth(aws_access_key=s3_access_key_id,
                    aws_secret_access_key=s3_secret_access_key,
                    aws_host=dedupe_s3_host,
                    aws_region=dedupe_s3_region,
                    aws_service=dedupe_s3_service)
   
    _filename, extension = path.splitext(producermessage.filename)
    filepath = producermessage.s3filepath
    if extension not in ['.pdf']:
        filepath = path.splitext(filepath)[0] + extension
    response= requests.get('{0}'.format(filepath), auth=auth,stream=True)
    
    if extension in ['.pdf']:
        reader = PdfReader(BytesIO(response.content))
        # "No of pages in {0} is {1} ".format(_filename, len(reader.pages)))
        pagecount = len(reader.pages)
    elif extension in ['.doc','.docx','.xls','.xlsx','.msg']:
        #"Extension different {0}, so need to download pdf here for pagecount!!".format(extension))
        pdfresponseofconverted = requests.get('{0}'.format(producermessage.s3filepath), auth=auth,stream=True)
        reader = PdfReader(BytesIO(pdfresponseofconverted.content))
        # "Converted PDF , No of pages in {0} is {1} ".format(_filename, len(reader.pages)))
        pagecount = len(reader.pages)


    sig = hashlib.sha1()
    for line in response.iter_lines():
        sig.update(line)
    
    return (sig.hexdigest(),pagecount)