import psycopg2
import os
from dotenv import load_dotenv
import logging
import request

load_dotenv()

DOCREVIEWER_DB_HOST = os.getenv('DOCREVIEWER_DB_HOST')
DOCREVIEWER_DB_NAME = os.getenv('DOCREVIEWER_DB_NAME') 
DOCREVIEWER_DB_USER= os.getenv('DOCREVIEWER_DB_USER') 
DOCREVIEWER_DB_PASSWORD= os.getenv('DOCREVIEWER_DB_PASSWORD') 
DOCREVIEWER_DB_PORT= os.getenv('FOI_DB_PORT')
FOI_DB_HOST = os.getenv('FOI_DB_HOST')
FOI_DB_NAME = os.getenv('FOI_DB_NAME') 
FOI_DB_USER= os.getenv('FOI_DB_USER') 
FOI_DB_PASSWORD= os.getenv('FOI_DB_PASSWORD') 
FOI_DB_PORT= os.getenv('FOI_DB_PORT')
REQUEST_STATUS =  os.getenv('REQUEST_STATUS', "Records Review")
REQUEST_LIMIT =  os.getenv('REQUEST_LIMIT', 3)
ACTIVEMQ_USERNAME=os.getenv('ACTIVEMQ_USERNAME')
ACTIVEMQ_PASSWORD=os.getenv('ACTIVEMQ_PASSWORD')
ACTIVEMQ_DESTINATION=  os.getenv('ACTIVEMQ_DESTINATION',"foidocextract")


def getdocreviewerdbconnection():
    conn = psycopg2.connect(
        host=DOCREVIEWER_DB_HOST,
        database=DOCREVIEWER_DB_NAME,
        user=DOCREVIEWER_DB_USER,
        password=DOCREVIEWER_DB_PASSWORD,port=DOCREVIEWER_DB_PORT)
    return conn

def getfoidbconnection():
    conn = psycopg2.connect(
        host=FOI_DB_HOST,
        database=FOI_DB_NAME,
        user=FOI_DB_USER,
        password=FOI_DB_PASSWORD,port=FOI_DB_PORT)
    return conn


def getrequestswithstatus():
    conn = getfoidbconnection()
    try:
        cursor = conn.cursor()
        query = '''
            SELECT DISTINCT fmr.foiministryrequestid, fmr.version , fmr.axisrequestid,
            fr.requesttype, fr.receiveddate
            FROM "FOIMinistryRequests" fmr
            JOIN "FOIRequestStatuses" frs ON fmr.requeststatusid = frs.requeststatusid
            JOIN "FOIRequests" fr ON fmr.foiministryrequestid = fr.foirequestid AND
            fmr.version = fr.version
            WHERE fmr."isactive"= true and frs."name" = %s limit %s::integer;
        '''
        parameters = (REQUEST_STATUS, REQUEST_LIMIT)
        cursor.execute(query, parameters)
        result = cursor.fetchall()
        return result
    except Exception as error:
        logging.error("Error in getrequestswithstatus")
        logging.error(error)
        raise
    finally:
        cursor.close()
        if conn is not None:
            conn.close()


def fetchdocumentsforextraction():
    try:
        requestresults = getrequestswithstatus()
        request_ids = [item["id"] for item in requestresults]
        conn = getdocreviewerdbconnection()
        cursor = conn.cursor()
        query = '''
            SELECT d.foiministryrequestid, d.documentid, d.documentmasterid , d.filename, dm.filepath
            FROM public."Documents" d
            INNER JOIN "DocumentMaster" dm 
                ON d.documentmasterid = dm.documentmasterid
            WHERE
                d.foiministryrequestid IN :%s
                AND EXISTS (
                            SELECT 1
                            FROM "DocumentHashCodes" dhc
                            INNER JOIN public."Documents" d2 
                                ON dhc.documentid = d2.documentid
                            WHERE d2.statusid IN (
                                SELECT statusid
                                FROM "DocumentStatus" 
                                WHERE "name" IN ('new', 'failed')
                            )
                            AND d2.documentid= d.documentid
                            GROUP BY dhc.rank1hash, d2.documentid, dhc.created_at
                            HAVING dhc.created_at = MIN(dhc.created_at)
                )
                AND  NOT EXISTS (
                        SELECT 1
                        FROM "DocumentDeleted" dd
                        WHERE dm.filepath LIKE dd.filepath || '%' 
                        AND (dm.filepath IS NOT NULL AND dd.deleted IS TRUE)
                    )
                GROUP BY d.foiministryrequestid, d.documentid, d.documentmasterid , d.filename, dm.filepath
                ORDER BY d.foiministryrequestid; 
        '''
        parameters = (request_ids)
        cursor.execute(query, parameters)
        result = cursor.fetchall()
        requests=[]
        for row in result:
            request= formatdocumentsrequest(row, requestresults)
            requests.append(request)
        print("Requests for extraction:",requests)
        #call activemq POST api
        pushdocstoactivemq(requests)
        #return requests
    except Exception as error:
        logging.error("Error in fetchdocumentsforextraction")
        logging.error(error)
        raise
    finally:
        cursor.close()
        if conn is not None:
            conn.close()


def pushdocstoactivemq(requests):
    url = "https://activemq-fc7a67-dev.apps.gold.devops.gov.bc.ca/api/message"
    username = ACTIVEMQ_USERNAME
    password = ACTIVEMQ_PASSWORD
    params = {
    "destination": "queue://"+ACTIVEMQ_DESTINATION
    }
    try:
        #Activemq POST request
        response = requests.post(url, auth=(username, password), params=params, json=requests)
        if response.status_code == 200:
            print("Success:", response.json())
        else:
            print(f"Error: {response.status_code}, {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Activemq request failed: {e}")



def formatdocumentsrequest(document,requestdetails):
    request_detail = [item for item in requestdetails if item["foiministryrequestid"] == document.foiministryrequestid]
    return {
        "RequestID": request_detail.axisrequestid,
        "RequestType": request_detail.requesttype,
        "ReceivedDate": request_detail.receiveddate,
        "MinistryRequestID": request_detail.foiministryrequestid,
        "RequestVersion": request_detail.version,
        "Documents": [
            {
            "DocumentID": document.documentid,
            "DocumentName": document.filename,
            "DocumentType": "PDF",
            "CreatedDate": document.created_at,
            "DocumentS3URL":document.filepath,
            #"Divisions":[{"DivisionID":"12213","Name":"Minister's Office"}]
            }
        ]
    }

if __name__ == "__main__":
    fetchdocumentsforextraction()
    


