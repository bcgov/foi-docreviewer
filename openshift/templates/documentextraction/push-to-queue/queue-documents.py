import psycopg2
import os
from dotenv import load_dotenv
import logging
import requests
import uuid
from datetime import datetime

load_dotenv()

DOCREVIEWER_DB_HOST = os.getenv('DOCREVIEWER_DB_HOST')
DOCREVIEWER_DB_NAME = os.getenv('DOCREVIEWER_DB_NAME') 
DOCREVIEWER_DB_USER= os.getenv('DOCREVIEWER_DB_USER') 
DOCREVIEWER_DB_PASSWORD= os.getenv('DOCREVIEWER_DB_PASSWORD') 
DOCREVIEWER_DB_PORT= os.getenv('DOCREVIEWER_DB_PORT')
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
            SELECT DISTINCT ON (fmr.foiministryrequestid) 
            fmr.foiministryrequestid, 
            fmr.version, 
            fmr.axisrequestid, 
            fr.requesttype, 
            fr.receiveddate,
            pa.iaocode AS programareacode,
            (SELECT JSON_AGG(
                JSON_BUILD_OBJECT(
                    'DivisionID', sub_fmd.divisionid,
                    'Name', pad.name
                )
            )
            FROM (
                SELECT DISTINCT fmd.divisionid
                FROM "FOIMinistryRequestDivisions" fmd
                WHERE fmd.foiministryrequest_id = fmr.foiministryrequestid
            ) sub_fmd
            LEFT JOIN "ProgramAreaDivisions" pad 
            ON sub_fmd.divisionid = pad.divisionid
            ) AS division
            FROM "FOIMinistryRequests" fmr
            JOIN "FOIRequestStatuses" frs 
                ON fmr.requeststatusid = frs.requeststatusid
            JOIN "FOIRequests" fr 
                ON fmr.foiministryrequestid = fr.foirequestid 
                AND fmr.version = fr.version
            LEFT JOIN "ProgramAreas" pa 
    	        ON fmr.programareaid = pa.programareaid
            WHERE fmr."isactive" = true 
            AND frs."name" = %s
            ORDER BY fmr.foiministryrequestid, fmr.version DESC;
        '''
        parameters = (REQUEST_STATUS,)
        cursor.execute(query, parameters)
        result = cursor.fetchall()
        cursor.close()
        if result is not None:
            requestsforextraction = []
            for entry in result:
                requestsforextraction.append({"foiministryrequestid": entry[0], "version": entry[1], "axisrequestid": entry[2],
                                  "requesttype": entry[3], "receiveddate": entry[4], "programareacode":entry[5], "divisions": entry[6]})
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
        #print("requestresults:",requestresults)
        if requestresults is not None:
            request_ids = [item["foiministryrequestid"] for item in requestresults]
            print("request_ids:",request_ids)
            conn = getdocreviewerdbconnection()
            cursor = conn.cursor()
            query = '''
                SELECT d.foiministryrequestid,     
                JSON_AGG(
                    JSON_BUILD_OBJECT(
                        'documentid', d.documentid, 
                        'filename', d.filename, 
                        'created_at', d.created_at, 
                        'filepath', dm.filepath, 
                        'attributes', da.attributes
                    )
                ) AS documents
                FROM "Documents" d
                INNER JOIN "DocumentMaster" dm 
                ON d.documentmasterid = dm.documentmasterid
                LEFT JOIN "DocumentAttributes" da 
                ON (dm.processingparentid IS NOT NULL AND dm.processingparentid = da.documentmasterid)
                OR (dm.processingparentid IS NULL AND dm.documentmasterid = da.documentmasterid)
                WHERE d.foiministryrequestid IN %s
                AND EXISTS (
                    SELECT 1 FROM "DocumentHashCodes" dhc
                    WHERE dhc.documentid = d.documentid
                    AND dhc.created_at = (
                        SELECT MIN(dhc_inner.created_at)
                        FROM "DocumentHashCodes" dhc_inner
                        WHERE dhc_inner.documentid = d.documentid
                    )
                )
                AND EXISTS (
                    SELECT 1 FROM "DocumentStatus" ds
                    WHERE ds.statusid = d.statusid
                    AND ds.name IN ('new', 'failed')
                )
                AND NOT EXISTS (
                    SELECT 1 FROM "DocumentDeleted" dd
                    WHERE dm.filepath LIKE dd.filepath || %s
                    AND dd.deleted IS TRUE
                )
                GROUP BY 
                    d.foiministryrequestid
                ORDER BY 
                    d.foiministryrequestid;
            '''
            parameters = (tuple(request_ids), '%')
            # print("\nparameters:",parameters)
            # print("\nQuery:",query)
            cursor.execute(query, parameters)
            result = cursor.fetchall()
            #breakpoint()
            cursor.close()
            if result is not None:
                requestswithdocs=[]
                for entry in result:
                    #print("\n\nDOCSS:",entry[1])
                    if entry[1]:
                        row={"foiministryrequestid": entry[0], "documents": entry[1]}
                        print("\n\nROW:::",row)
                        requestswithdocs.append(row)
                        #requestsforextraction.append(formatdocumentsrequest(row, requestresults))
                return requestresults, requestswithdocs
                #print("Requests for extraction:",requestsforextraction)
                logging.info("No documents to queue for extraction!")
            else:
                logging.info("No documents found for extraction!")
        logging.info("No requests found for document extraction!")
        return None
    except Exception as error:
        logging.error("Error in fetchdocumentsforextraction")
        logging.error(error)
        raise
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def formatdocumentsrequest(requestswithdocs,requestdetails):
    limited_requestdetails= sortandlimitrequests(requestswithdocs,requestdetails)
    print("\n\nlimited_requestdetails:",limited_requestdetails)
    #print("\n\nrequestdetails:",requestdetails)
    formatted_requests=[]
    for request in limited_requestdetails:
        requestdocuments = [item for item in requestswithdocs if item["foiministryrequestid"] == request["foiministryrequestid"]]
        print("\n\nrequest:",request)
        formatted_documents=[]
        for document in requestdocuments[0]["documents"]:
            filename = document["filename"]
            fileextension = os.path.splitext(document["filename"])[1].lower()
            if fileextension not in [".png", ".jpg", ".jpeg", ".gif"]:
                filename = os.path.splitext(filename)[0] + ".pdf"
            request_divisions= request["divisions"]
            print("\nREQUEST_DIVISIONS:",request_divisions)
            print("\nDOCUMENT_DIVISIONS:",document["attributes"]["divisions"][0])
            if request_divisions and document["attributes"]["divisions"][0]:
                documentdivision = [item for item in request_divisions if item["DivisionID"] == document["attributes"]["divisions"][0]["divisionid"]]
            else:
                documentdivision = {'DivisionID': 0,'Name': ""}
            #print("\ndocumentdivision:",documentdivision)
            formatted_documents.append(
                {
                    "DocumentID": document["documentid"],
                    "DocumentName": filename ,
                    "DocumentType": fileextension[1:].upper(),
                    "CreatedDate": convert_date_string_dynamic_preserve_time(document["created_at"]),
                    "DocumentS3URL":document["filepath"],
                    "Divisions": documentdivision
                }
            )
        formatted_requests.append({
            "RequestNumber": request["axisrequestid"],
            "RequestType": request["requesttype"],
            "ReceivedDate": convert_datetime_dynamic(request["receiveddate"],"receiveddate"),
            "MinistryRequestID": str(request["foiministryrequestid"]),
            "MinistryCode":request["programareacode"],
            "RequestMiscInfo":"",
            "Documents": formatted_documents
        })
        print("\n\nformatted_requests:",formatted_requests)
    return formatted_requests

def convert_datetime_dynamic(date_obj,datefield):
    # Example logic: Set to the 1st day of the next month
    if date_obj.month == 12:
        updated_date = date_obj.replace(year=date_obj.year + 1, month=1, day=1)
    else:
        updated_date = date_obj.replace(month=date_obj.month + 1, day=1)
    if datefield == "receiveddate":
        result= updated_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        result= updated_date.strftime("%Y-%m-%dT%H:%M:%S")
    return result

def convert_date_string_dynamic_preserve_time(input_date_str):
    date_obj = datetime.strptime(input_date_str, "%Y-%m-%dT%H:%M:%S.%f")
    # Example logic: Increment the month and reset the day to 1
    if date_obj.month == 12:
        updated_date = date_obj.replace(year=date_obj.year + 1, month=1, day=1)
    else:
        updated_date = date_obj.replace(month=date_obj.month + 1, day=1)
    return updated_date.strftime("%Y-%m-%dT%H:%M:%SZ")



def sortandlimitrequests(requestswithdocs, requestdetails):
    request_limit= int(REQUEST_LIMIT)
    valid_request_ids = {item["foiministryrequestid"] for item in requestswithdocs}
    # Sort the requestdetails by 'receiveddate' in descending order
    sorted_requestdetails = sorted(
        requestdetails, 
        key=lambda x: x["receiveddate"], 
        reverse=True
    )
    filtered_requestdetails = [
        item for item in sorted_requestdetails if item["foiministryrequestid"] in valid_request_ids
    ]
    # Limit top most recent requests according to the limit given
    limited_requestdetails = filtered_requestdetails[:request_limit]
    return limited_requestdetails

def fetchandqueuedocsforextraction():
    requestresults, requestswithdocs= fetchdocumentsforextraction()
    if requestswithdocs:
        requestsforextraction= formatdocumentsrequest(requestswithdocs, requestresults)
        #print("\n\nRequestsforextraction:",requestsforextraction)
        logging.info("Pushing requests to queue for extraction!")
        #call activemq POST api
        activemqresponse= pushdocstoactivemq(requestsforextraction)
        return activemqresponse


def pushdocstoactivemq(requestsforextraction):
    url = "https://activemq-fc7a67-dev.apps.gold.devops.gov.bc.ca/api/message"
    username = ACTIVEMQ_USERNAME
    password = ACTIVEMQ_PASSWORD
    params = {
    "destination": "queue://"+ACTIVEMQ_DESTINATION
    }
    try:
        if requestsforextraction:
            formattedjson= formatbatch(requestsforextraction)
            print("\n\nFINAL JSON:", formattedjson)
            #Activemq POST request
            response = requests.post(url, auth=(username, password), params=params, json=formattedjson)
            if response.status_code == 200:
                print("Success:", response.text)
                #Update Documents status to pushedtoqueue
                #updatedocumentsstatus(requestsforextraction)
            else:
                print(f"Error: {response.status_code}, {response.text}")
            return response
        return None
    except requests.exceptions.RequestException as e:
        print(f"Activemq request failed: {e}")


def formatbatch(requestsforextraction):
    return {
        "BatchID": str(uuid.uuid4()),
        "Date": convert_datetime_dynamic(datetime.now(),"batchdate"),
        "Requests": requestsforextraction
    }

def updatedocumentsstatus(requestsforextraction):
    try:
        document_ids = []
        for request in requestsforextraction:
            for document in request.get("Documents", []):
                document_ids.append(document["DocumentID"])
        print("Extracted Document IDs:", document_ids)
        conn = getdocreviewerdbconnection()
        cursor = conn.cursor()
        cursor.execute('''update "Documents" SET statusid = (SELECT statusid
		              FROM "DocumentStatus" 
		              WHERE "name" = 'pushedtoqueue') WHERE documentid IN %s''',
            (tuple(document_ids),))
        conn.commit()
        cursor.close()
    except(Exception) as error:
        print("Exception while executing func updateredactionstatus, Error : {0} ".format(error))
        raise
    finally:
        if conn is not None:
            conn.close() 

# def generatebatchid(prefix="BATCH"):
#     random_number = str(uuid.uuid4().int)[:4]
#     return f"{prefix}{random_number}"


if __name__ == "__main__":
    fetchandqueuedocsforextraction()
    


