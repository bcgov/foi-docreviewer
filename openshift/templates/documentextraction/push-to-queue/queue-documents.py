import psycopg2
import os
from dotenv import load_dotenv
import logging
import requests

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
        cursor.close()
        if result is not None:
            requestsforextraction = []
            for entry in result:
                requestsforextraction.append({"foiministryrequestid": entry[0], "version": entry[1], "axisrequestid": entry[2],
                                  "requesttype": entry[3], "receiveddate": entry[4]})
                return requestsforextraction
        return None
    except Exception as error:
        logging.error("Error in getrequestswithstatus")
        logging.error(error)
        raise
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def fetchdocumentsforextraction():
    try:
        requestresults = getrequestswithstatus()
        print("requestresults:",requestresults)
        if requestresults is not None:
            request_ids = [item["foiministryrequestid"] for item in requestresults]
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
            cursor.close()
            requestsforextraction=[]
            for row in result:
                requestsforextraction.append(formatdocumentsrequest(row, requestresults))
                requests.append(requestsforextraction)
            print("Requests for extraction:",requestsforextraction)
            logging.info("Pushing requests to queue for extraction!")
            #call activemq POST api
            activemqresponse= pushdocstoactivemq(requestsforextraction)
            return activemqresponse
        logging.info("No requests found for document extraction!")
        return requestresults
    except Exception as error:
        logging.error("Error in fetchdocumentsforextraction")
        logging.error(error)
        raise
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def pushdocstoactivemq(requestsforextraction):
    url = "https://activemq-fc7a67-dev.apps.gold.devops.gov.bc.ca/api/message"
    username = ACTIVEMQ_USERNAME
    password = ACTIVEMQ_PASSWORD
    params = {
    "destination": "queue://"+ACTIVEMQ_DESTINATION
    }
    try:
        #Activemq POST request
        response = requests.post(url, auth=(username, password), params=params, json=requestsforextraction)
        if response.status_code == 200:
            print("Success:", response.json())
        else:
            print(f"Error: {response.status_code}, {response.text}")
        return response
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
    


