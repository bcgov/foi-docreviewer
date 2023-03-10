from . import getdbconnection,gets3credentialsobject
from psycopg2 import sql
from os import path
import psycopg2
import requests
from aws_requests_auth.aws_auth import AWSRequestsAuth
import hashlib
import mimetypes
from utils import gets3credentialsobject, pdfstitch_s3_region,pdfstitch_s3_host,pdfstitch_s3_service,pdfstitch_s3_env

def __getcredentialsbybcgovcode(bcgovcode):
    _conn = getdbconnection()
    s3cred = None
    try:                              
        cur = _conn.cursor()
        _sql = sql.SQL("SELECT  attributes FROM {0} WHERE bucket='{1}'and category='Records'".format('public."DocumentPathMapper"','{0}-{1}'.format(bcgovcode.lower(),pdfstitch_s3_env.lower())))
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
                    aws_host=pdfstitch_s3_host,
                    aws_region=pdfstitch_s3_region,
                    aws_service=pdfstitch_s3_service)
   
    _filename, extension = path.splitext(producermessage.filename)
    filepath = producermessage.s3filepath
    if extension not in ['.pdf']:
        filepath = path.splitext(filepath)[0] + extension
    response= requests.get('{0}'.format(filepath), auth=auth,stream=True)
    sig = hashlib.sha1()
    for line in response.iter_lines():
        sig.update(line)
    
    return sig.hexdigest()


def gets3documentbytearray(producermessage): 
    
    s3credentials = __getcredentialsbybcgovcode(producermessage.bcgovcode)

    s3_access_key_id= s3credentials.s3accesskey
    s3_secret_access_key= s3credentials.s3secretkey

    auth = AWSRequestsAuth(aws_access_key=s3_access_key_id,
                    aws_secret_access_key=s3_secret_access_key,
                    aws_host=pdfstitch_s3_host,
                    aws_region=pdfstitch_s3_region,
                    aws_service=pdfstitch_s3_service)
    _filename, extension = path.splitext(producermessage.filename)
    filepath = producermessage.s3filepath
    if extension in ['.pdf']:
        filepath = path.splitext(filepath)[0] + extension
    response= requests.get('{0}'.format(filepath), auth=auth,stream=True)
    return response.content

def uploadbytes(filename, bytes, requestnumber, bcgovcode):
    s3credentials = __getcredentialsbybcgovcode(bcgovcode)

    s3_access_key_id= s3credentials.s3accesskey
    s3_secret_access_key= s3credentials.s3secretkey
    formsbucket = bcgovcode.lower()+'-'+pdfstitch_s3_env.lower() #pdfstitch_s3_bucket
    try: 
        auth = AWSRequestsAuth(aws_access_key=s3_access_key_id,
        aws_secret_access_key=s3_secret_access_key,
        aws_host=pdfstitch_s3_host,
        aws_region=pdfstitch_s3_region,
        aws_service=pdfstitch_s3_service) 

        s3uri = 'https://{0}/{1}/{2}/{3}'.format(pdfstitch_s3_host,formsbucket, requestnumber, filename)        
        response = requests.put(s3uri, data=None, auth=auth)
        header = {
                'X-Amz-Date': response.request.headers['x-amz-date'],
                'Authorization': response.request.headers['Authorization'],
                'Content-Type': 'application/octet-stream' #mimetypes.MimeTypes().guess_type(filename)[0]
        }

        #upload to S3
        requests.put(s3uri, data=bytes, headers=header)
        attachmentobj = {"success": True, 'filename': filename, 'documentpath': s3uri}
    except Exception as ex:
        print(ex)
        attachmentobj = {"success": False, 'filename': filename, 'documentpath': None}   
    return attachmentobj