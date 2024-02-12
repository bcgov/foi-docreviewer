from utils.dbconnection import getdbconnection
from psycopg2 import sql
from os import path
import psycopg2
import requests
from aws_requests_auth.aws_auth import AWSRequestsAuth
from utils.jsonmessageparser import gets3credentialsobject
from utils.foidocumentserviceconfig import docservice_db_user,docservice_db_port,docservice_s3_host,docservice_db_name,docservice_s3_region,docservice_s3_service,docservice_failureattempt
import logging

def getcredentialsbybucketname(bucketname):
    _conn = getdbconnection()
    s3cred = None
    #bucket = '{0}-{1}-e'.format(bcgovcode.lower(),pdfstitch_s3_env.lower())
    try:                              
        cur = _conn.cursor()
        _sql = sql.SQL("SELECT  attributes FROM {0} WHERE bucket='{1}'and category='Records'".format('public."DocumentPathMapper"',bucketname))
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

def uploadbytes(filename, filebytes, s3uri):
    bucketname= s3uri.split("/")[3]
    s3credentials= getcredentialsbybucketname(bucketname)
    s3_access_key_id= s3credentials.s3accesskey
    s3_secret_access_key= s3credentials.s3secretkey
    retry = 0
    while True:
        try: 
            auth = AWSRequestsAuth(aws_access_key=s3_access_key_id,
            aws_secret_access_key=s3_secret_access_key,
            aws_host=docservice_s3_host,
            aws_region=docservice_s3_region,
            aws_service=docservice_s3_service) 
            s3uri= s3uri+filename    
            response = requests.put(s3uri, data=None, auth=auth)
            header = {
                    'X-Amz-Date': response.request.headers['x-amz-date'],
                    'Authorization': response.request.headers['Authorization'],
                    'Content-Type': 'application/octet-stream' #mimetypes.MimeTypes().guess_type(filename)[0]
            }

            #upload to S3
            uploadresponse= requests.put(s3uri, data=filebytes, headers=header)
            uploadobj = {"uploadresponse": uploadresponse, "filename": filename, "documentpath": s3uri}
            return uploadobj
        except Exception as ex:
            if retry > int(docservice_failureattempt):
                logging.error("Error in uploading document to S3")
                logging.error(ex)
                uploadobj = {"success": False, "filename": filename, "documentpath": None}
                raise ValueError(uploadobj, ex)
            logging.info(f"uploadbytes s3retry = {retry}")
            
            retry += 1
            continue
        finally:
            if filebytes:
                filebytes = None
            del filebytes