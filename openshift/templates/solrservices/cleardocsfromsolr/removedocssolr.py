import psycopg2
import os
from dotenv import load_dotenv
import logging
import requests
from datetime import datetime
import base64

load_dotenv()

DOCREVIEWER_DB_HOST = os.getenv('DOCREVIEWER_DB_HOST')
DOCREVIEWER_DB_NAME = os.getenv('DOCREVIEWER_DB_NAME') 
DOCREVIEWER_DB_USER= os.getenv('DOCREVIEWER_DB_USER') 
DOCREVIEWER_DB_PASSWORD= os.getenv('DOCREVIEWER_DB_PASSWORD') 
DOCREVIEWER_DB_PORT= os.getenv('DOCREVIEWER_DB_PORT')
SOLR_ENDPOINT=os.getenv('SOLR_ENDPOINT')
SOLR_USERNAME=os.getenv('SOLR_USERNAME')
SOLR_PASSWORD=os.getenv('SOLR_PASSWORD')



def getdocreviewerdbconnection():
    conn = psycopg2.connect(
        host=DOCREVIEWER_DB_HOST,
        database=DOCREVIEWER_DB_NAME,
        user=DOCREVIEWER_DB_USER,
        password=DOCREVIEWER_DB_PASSWORD,port=DOCREVIEWER_DB_PORT)
    return conn

def getdocumentstoremovesolr():
    try:              
        conn = getdocreviewerdbconnection()
        cursor = conn.cursor()
        query = '''
                SELECT 
                DISTINCT D.documentid
                ,DD.documentdeletedid
                ,DM.filepath as ACTUALFILEPATH
                ,DD.removedfromsolr
                FROM public."Documents" D JOIN public."DocumentMaster" DM on D.documentmasterid = DM.documentmasterid 
                JOIN public."DocumentDeleted" DD ON DD.filepath = regexp_replace(DM.filepath, '\.[a-zA-Z0-9]+$', '') 
                WHERE D.statusid in (SELECT statusid FROM public."DocumentStatus" WHERE name in ('pushedtoqueue','extractioncompleted')) and  removedfromsolr=false
                ORDER BY D.documentid LIMIT 50
            '''   
        cursor.execute(query)    
        documenttoremovefromsolr = cursor.fetchall()
            
        cursor.close()
        if documenttoremovefromsolr is not None:
            # Loop through the documentsdeleted
            for document in documenttoremovefromsolr:
                documentid, documentdeletedid, ACTUALFILEPATH,removedfromsolr = document  # Unpack the row
                print(f"documentid: {documentid}, documentdeletedid: {documentdeletedid}, ACTUALFILEPATH: {ACTUALFILEPATH},removedfromsolr:{removedfromsolr}")
                status = posttosolr(ACTUALFILEPATH)
                if(status == True):
                   updatestatusondb(documentdeletedid)     
        else:
            logging.info("No documents found for SOLR removal!")
       
        return None
    except Exception as error:
        logging.error("Error in SOLR Document delete Process.")
        logging.error(error)
        raise
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

def posttosolr(documenturl):
    # Define the Solr URL
    url = "{0}/update?commit=true".format(SOLR_ENDPOINT)

    # Define the XML body
    xml_body = """<delete><query>foidocumenturl:"{0}"</query></delete>""".format(documenturl)

    # Authentication credentials
    username = SOLR_USERNAME
    password = SOLR_PASSWORD
    # Combine username and password with a colon
    credentials = f"{username}:{password}"

    # Encode the credentials in Base64
    encoded_credentials = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")

   
     # Set the headers
    headers = {
        "Content-Type": "application/xml",
        "Authorization": f"Basic {encoded_credentials}"
    }

    try:
    # Make the POST request with Basic Auth
        response = requests.post(url, data=xml_body, headers=headers, auth=(username, password))

        # Check the response
        if response.status_code == 200:
            print("Request successful:", response.text)
            return True
        else:
            print(f"Request failed with status code {response.status_code}: {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return False

def updatestatusondb(documentdeleteid):
    try:
        
        conn = getdocreviewerdbconnection()
        cursor = conn.cursor()
        cursor.execute('''update public."DocumentDeleted" SET removedfromsolr = true WHERE documentdeletedid = %s''',
            (documentdeleteid,))
        conn.commit()
        cursor.close()
    except(Exception) as error:
        print("Exception while executing func updatestatusondb on SOLR document delete, Error : {0} ".format(error))
        raise
    finally:
        if conn is not None:
            conn.close()    

if __name__ == "__main__":
    getdocumentstoremovesolr()            
