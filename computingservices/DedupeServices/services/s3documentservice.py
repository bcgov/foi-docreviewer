from . import getdbconnection,gets3credentialsobject
from . import foidedupehashcalulator
from psycopg2 import sql
import json
import psycopg2
import requests
from aws_requests_auth.aws_auth import AWSRequestsAuth
import hashlib
from utils import gets3credentialsobject,getdedupeproducermessage, dedupe_s3_region,dedupe_s3_host,dedupe_s3_service,dedupe_s3_env

def __getcredentialsbybcgovcode(bcgovcode):
    _conn = getdbconnection()
    s3cred = None
    try:                              
        cur = _conn.cursor()
        _sql = sql.SQL("SELECT  attributes FROM {0} WHERE bucket='{1}'and category='Records'".format('public."DocumentPathMapper"','{0}-{1}'.format(bcgovcode.lower(),dedupe_s3_env.lower())))
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

    s3_access_key_id= s3credentials.s3accesskey
    s3_secret_access_key= s3credentials.s3secretkey
        
    auth = AWSRequestsAuth(aws_access_key=s3_access_key_id,
                    aws_secret_access_key=s3_secret_access_key,
                    aws_host=dedupe_s3_host,
                    aws_region=dedupe_s3_region,
                    aws_service=dedupe_s3_service)
   
    response= requests.get('https://{0}/{1}'.format(dedupe_s3_host,producermessage.s3filepath), auth=auth,stream=True)
    sig = hashlib.sha1()
    for line in response.iter_lines():
        sig.update(line)
    
    return sig.hexdigest()