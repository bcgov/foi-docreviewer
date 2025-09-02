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
REQUEST_LIMIT =  int(os.getenv('REQUEST_LIMIT', 5))
ACTIVEMQ_URL= os.getenv('ACTIVEMQ_URL')
ACTIVEMQ_USERNAME=os.getenv('ACTIVEMQ_USERNAME')
ACTIVEMQ_PASSWORD=os.getenv('ACTIVEMQ_PASSWORD')
ACTIVEMQ_DESTINATION= os.getenv('ACTIVEMQ_DESTINATION',"foidocextract")
FULL_CONTROL = os.getenv("FULL_CONTROL", "false").lower() == "true"

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
    from_date = os.getenv("FROM_DATE", "2025-02-20")

    if FULL_CONTROL:
        to_date = os.getenv("TO_DATE")
    else:
        to_date = datetime.now().strftime("%Y-%m-%d")
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
                    ON fmr.foirequest_id = fr.foirequestid 
                    AND fmr.foirequestversion_id = fr.version
                LEFT JOIN "ProgramAreas" pa 
                    ON fmr.programareaid = pa.programareaid
                WHERE fmr."isactive" = true 
                AND fr.receiveddate >= %s
                AND fr.receiveddate <= %s
                AND EXISTS (
                    SELECT 1
                    FROM "FOIMinistryRequests" fm2
                    INNER JOIN "FOIRequestStatuses" fs2 
                        ON fm2.requeststatusid = fs2.requeststatusid
                    WHERE fm2.foiministryrequestid = fmr.foiministryrequestid
                    AND fs2."name" = %s
                )
                ORDER BY fmr.foiministryrequestid, fmr.version DESC;
        '''
        parameters = (from_date, to_date, REQUEST_STATUS,)
        cursor.execute(query, parameters)
        result = cursor.fetchall()
        cursor.close()
        if result:
            requestsforextraction = []
            for entry in result:
                requestsforextraction.append({"foiministryrequestid": entry[0], "version": entry[1], "axisrequestid": entry[2],
                                  "requesttype": entry[3], "receiveddate": entry[4], "programareacode":entry[5], "divisions": entry[6]})
            return requestsforextraction
        return []
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
    cursor = None
    conn = None
    try:
        requestresults = getrequestswithstatus()
        if requestresults:
            request_ids = [item["foiministryrequestid"] for item in requestresults]
            print("Total requests:", len(request_ids), "| Request IDs:", request_ids)

            conn = getdocreviewerdbconnection()
            cursor = conn.cursor()
            query = '''
                SELECT d.foiministryrequestid,     
                JSON_AGG(
                    JSON_BUILD_OBJECT(
                        'documentid', d.documentid, 
                        'filename', d.filename, 
                        'created_at', d.created_at,
                        'selectedfileprocessversion', d.selectedfileprocessversion, 
                        'filepath', dm.filepath,
                        'compressedfilepath', (
                            CASE 
                                WHEN dm.processingparentid IS NOT NULL THEN parent_dm.compressedfilepath
                                ELSE dm.compressedfilepath
                            END
                        ),
                        'ocrfilepath', (
                            CASE 
                                WHEN dm.processingparentid IS NOT NULL THEN parent_dm.ocrfilepath
                                ELSE dm.ocrfilepath
                            END
                        )
                    )
                ) AS documents
                FROM "Documents" d
                INNER JOIN "DocumentMaster" dm 
                ON d.documentmasterid = dm.documentmasterid
                LEFT JOIN "DocumentMaster" parent_dm 
                ON dm.processingparentid = parent_dm.documentmasterid
                WHERE d.foiministryrequestid IN %s AND d.incompatible = False
                AND NOT EXISTS (
                    SELECT 1 FROM "DocumentExtractionJob" dej WHERE dej.documentid = d.documentid
                    and (dej.status = 'extractionsucceeded' OR dej.status = 'extractionjobfailed')
                )
                GROUP BY 
                    d.foiministryrequestid
                LIMIT %s;
            '''
            parameters = (tuple(request_ids), REQUEST_LIMIT)
            cursor.execute(query, parameters)
            result = cursor.fetchall()
            cursor.close()
            if result:
                requestswithdocs=[]
                for entry in result:
                    if entry[1]:
                        row={"foiministryrequestid": entry[0], "documents": entry[1]}
                        requestswithdocs.append(row)
                        #requestsforextraction.append(formatdocumentsrequest(row, requestresults))
                return requestresults, requestswithdocs
            else:
                print("No documents found for extraction!")
                logging.info("No documents found for extraction!")
        logging.info("No requests found for document extraction!")
        return requestresults, []
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
    #print("\n\nlimited_requestdetails:",limited_requestdetails)
    formatted_requests=[]
    for request in limited_requestdetails:
        requestdocuments = [item for item in requestswithdocs if item["foiministryrequestid"] == request["foiministryrequestid"]]
        formatted_documents=[]
        for document in requestdocuments[0]["documents"]:
            filename = document["filename"]
            fileextension = os.path.splitext(document["filename"])[1].lower()
            if fileextension not in [".png", ".jpg", ".jpeg", ".gif"]:
                filename = os.path.splitext(filename)[0] + ".pdf"
            # request_divisions= request["divisions"]
            # print("\nREQUEST_DIVISIONS:",request_divisions)
            # print("\nDOCUMENT_DIVISIONS:",document["attributes"]["divisions"][0])
            # if request_divisions and document["attributes"]["divisions"][0]:
            #     documentdivision = [item for item in request_divisions if item["DivisionID"] == document["attributes"]["divisions"][0]["divisionid"]]
            # else:
            documentdivision = {'DivisionID': 0,'Name': ""}
            if "selectedfileprocessversion" in document and document["selectedfileprocessversion"] == 1:
                document_s3_url = document["filepath"]
            elif "ocrfilepath" in document and document["ocrfilepath"]:
                document_s3_url = document["ocrfilepath"]
            elif "compressedfilepath" in document and document["compressedfilepath"]:
                document_s3_url = document["compressedfilepath"]
            else:
                document_s3_url = document["filepath"]
            formatted_documents.append(
                {
                    "DocumentID": document["documentid"],
                    "DocumentName": filename ,
                    "DocumentType": fileextension[1:].upper(),
                    "CreatedDate": reformat_datetime(document["created_at"], "created_at"),
                    "DocumentS3URL": document_s3_url,
                    "Divisions": documentdivision
                }
            )
        formatted_requests.append({
            "RequestNumber": request["axisrequestid"],
            "RequestType": request["requesttype"],
            "ReceivedDate": reformat_datetime(request["receiveddate"],"receiveddate"),
            "MinistryRequestID": str(request["foiministryrequestid"]),
            "MinistryCode":request["programareacode"],
            "RequestMiscInfo":"",
            "Documents": formatted_documents
        })
        #print("\n\nformatted_requests:",formatted_requests)
    return formatted_requests

    
def reformat_datetime(input_date, datefield):
    try:
        if isinstance(input_date, datetime):
            dt = input_date
        else:
            input_date_str = str(input_date)
            formats_to_try = [
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S",
            ]
            for fmt in formats_to_try:
                try:
                    dt = datetime.strptime(input_date_str, fmt)
                    break
                except ValueError:
                    continue
            else:
                raise ValueError("Unsupported date format")
        if datefield == "batchdate":
            return dt.strftime("%Y-%m-%dT%H:%M:%S")
        else:
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception as e:
        raise ValueError(f"Failed to reformat datetime '{input_date}' for field '{datefield}': {e}")


# Keeping only sorting & removed the limit
def sortandlimitrequests(requestswithdocs, requestdetails):
    #request_limit= int(REQUEST_LIMIT)
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
    #limited_requestdetails = filtered_requestdetails[:request_limit]
    return filtered_requestdetails

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
    url = ACTIVEMQ_URL
    username = ACTIVEMQ_USERNAME
    password = ACTIVEMQ_PASSWORD
    params = {
    "destination": "queue://"+ACTIVEMQ_DESTINATION
    }
    try:
        if requestsforextraction:
            formattedjson= formatbatch(requestsforextraction)
            #Activemq POST request
            response = requests.post(url, auth=(username, password), params=params, json=formattedjson)
            if response.status_code == 200:
                print("Success:", response.text)
                #Update Documents status to pushedtoqueue
                updatedocumentsstatus(requestsforextraction)
            else:
                print(f"Error: {response.status_code}, {response.text}")
            return response
        return None
    except requests.exceptions.RequestException as e:
        print(f"Activemq request failed: {e}")


def formatbatch(requestsforextraction):
    return {
        "BatchID": str(uuid.uuid4()),
        "Date": reformat_datetime(datetime.now(),"batchdate"),
        "Requests": requestsforextraction
    }

def updatedocumentsstatus(requestsforextraction):
    try:
        document_ids = []
        for request in requestsforextraction:
            for document in request.get("Documents", []):
                document_ids.append(document["DocumentID"])
        print("Total documents:", len(document_ids), "| Extracted Document IDs:", document_ids)
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
    

