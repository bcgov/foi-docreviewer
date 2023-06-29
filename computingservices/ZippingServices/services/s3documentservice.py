
from psycopg2 import sql
from os import path
import psycopg2
import requests
from aws_requests_auth.aws_auth import AWSRequestsAuth
from utils import gets3credentialsobject,getdbconnection
from utils.foizipperconfig import *
import logging

def getcredentialsbybcgovcode(bcgovcode):
    _conn = getdbconnection()
    s3cred = None
    bucket = '{0}-{1}-e'.format(bcgovcode.lower(),s3_env.lower())
    try:                              
        cur = _conn.cursor()
        _sql = sql.SQL("SELECT  attributes FROM {0} WHERE bucket='{1}'and category='Records'".format('public."DocumentPathMapper"',bucket))
        cur.execute(_sql)
        attributes = cur.fetchone()
        if attributes is not None:
            s3cred = gets3credentialsobject(str(attributes[0]))
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        logging.error(error)
    finally:
        if _conn is not None:
            _conn.close() 

    return s3cred


def gets3documentbytearray(file, s3credentials):
    retry = 0
    filepath = file['s3uripath']
    while True:
        try:
            s3_access_key_id= s3credentials.s3accesskey
            s3_secret_access_key= s3credentials.s3secretkey

            auth = AWSRequestsAuth(aws_access_key=s3_access_key_id,
                            aws_secret_access_key=s3_secret_access_key,
                            aws_host=s3_host,
                            aws_region=s3_region,
                            aws_service=s3_service)
            response= requests.get(filepath, auth=auth,stream=True)
            return response.content
        except Exception as ex:
            if retry > int(failureattempt):
                logging.error("Error in connecting S3.")
                logging.error(ex)
                raise
            retry += 1
            continue


def uploadbytes(filename, filebytes, requestnumber, bcgovcode, s3credentials):

    s3_access_key_id= s3credentials.s3accesskey
    s3_secret_access_key= s3credentials.s3secretkey
    formsbucket = bcgovcode.lower()+'-'+s3_env.lower()+'-e'
    retry = 0
    while True:
        try: 
            auth = AWSRequestsAuth(aws_access_key=s3_access_key_id,
            aws_secret_access_key=s3_secret_access_key,
            aws_host=s3_host,
            aws_region=s3_region,
            aws_service=s3_service) 

            s3uri = 'https://{0}/{1}/{2}/{3}'.format(s3_host,formsbucket, requestnumber, filename)        
            response = requests.put(s3uri, data=None, auth=auth)
            header = {
                    'X-Amz-Date': response.request.headers['x-amz-date'],
                    'Authorization': response.request.headers['Authorization'],
                    'Content-Type': 'application/octet-stream' #mimetypes.MimeTypes().guess_type(filename)[0]
            }

            #upload to S3
            requests.put(s3uri, data=filebytes, headers=header)
            attachmentobj = {"success": True, "filename": filename, "documentpath": s3uri}
            return attachmentobj
        except Exception as ex:
            if retry > int(failureattempt):
                logging.error("Error in uploading document to S3")
                logging.error(ex)
                attachmentobj = {"success": False, "filename": filename, "documentpath": None}
                raise ValueError(attachmentobj, ex)
            logging.info(f"uploadbytes s3retry = {retry}")
            
            retry += 1
            continue
        finally:
            if filebytes:
                filebytes = None
            del filebytes