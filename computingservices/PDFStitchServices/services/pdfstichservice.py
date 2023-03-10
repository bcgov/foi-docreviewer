
from .s3documentservice import gets3documentbytearray, uploadbytes, getcredentialsbybcgovcode
from . import jsonmessageparser
import traceback
from pypdf import PdfReader, PdfWriter
from io import BytesIO
from multiprocessing.pool import ThreadPool as Pool
import json


def processmessage(_message):
    decoder = json.JSONDecoder()
    requestnumber = _message.requestnumber
    print("requestnumber === ",requestnumber)
    bcgovcode = _message.bcgovcode
    print("bcgovcode === ",bcgovcode)
    attributes = decoder.decode(_message.attributes)    
    print("attributes === ",attributes)
    print("attributes length = ", len(attributes))
    s3credentials = getcredentialsbybcgovcode(bcgovcode)
 
    try:
        pool = Pool(len(attributes))
        # loop through the atributes (currently divisions)
        for division in attributes:
            print("division = ",division)
            # pdfstitchbasedondivision(requestnumber, division, bcgovcode)
            pool.apply_async(pdfstitchbasedondivision, (requestnumber, division, s3credentials, bcgovcode))
        
        pool.close()
        pool.join()
    except (Exception) as error:
        print('error with Thread Pool: ', error)
 
def pdfstitchbasedondivision(requestno, division, s3credentials, bcgovcode):
    try:
        print("division files : ",division.get('files'))
        count = 0
        writer = PdfWriter()
        for file in division.get('files'):
            if count < len(division.get('files')):
                print("file = ", file)
                _message = json.dumps({str(key): str(value) for (key, value) in file.items()})
                _message = _message.replace("b'","'").replace("'",'') 
                producermessage = jsonmessageparser.getpdfstitchfilesproducermessage(_message)              
                print(file.get('filename'))
                docbytes = getdocumentbytearray(producermessage, s3credentials)
                writer = mergepdf(docbytes, writer)
                count += 1
        if writer:
            print("*********************write to PDF**********************")
            savetos3(writer, requestno + division.get('division')+'.pdf', 'EDU-2022-12345', bcgovcode, s3credentials)          
    except(Exception) as error:
        print('error with item: ', error)

def getdocumentbytearray(message, s3credentials):
    try:
        docbytearray = gets3documentbytearray(message, s3credentials)
        return docbytearray
    except(Exception) as error:
        print("error in getting the bytearray >> ",error)
        raise

def uploadstitchedpdf(filename, bytesarray, requestnumber, bcgovcode, s3credentials):
    try:
        print("filename = ", filename)
        docobj = uploadbytes(filename, bytesarray, requestnumber, bcgovcode, s3credentials)
        print(docobj)
        return docobj
    except(Exception) as error:
        print("error in writing the bytearray >> ", error)
        raise

def mergepdf(raw_bytes_data, writer ):
    reader = PdfReader(BytesIO(raw_bytes_data))
    print("**************reader*****************") 
    
    print("**************writer*****************") 
    # Add all pages to the writer
    for page in reader.pages:
        print("**************Add Page*****************") 
        writer.add_page(page)
    return writer
    
def savetos3(writer, filename, requestnumber, bcgovcode, s3credentials):
    with BytesIO() as bytes_stream:
        writer.write(bytes_stream)
        print("**************writer.write*****************") 
        bytes_stream.seek(0)
        uploadstitchedpdf(filename, bytes_stream, requestnumber, bcgovcode, s3credentials)