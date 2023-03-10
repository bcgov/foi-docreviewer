
from .s3documentservice import gets3documentbytearray, uploadbytes
# from .dedupedbservice import savedocumentdetails, recordjobstart, recordjobend
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
    attributes = decoder.decode(_message.attributes)    
    print("attributes === ",attributes)
    print("attributes length = ", len(attributes))
 
    try:
        # pool = Pool(len(attributes))
        # loop through the atributes (currently divisions)
        for division in attributes:
            print("division = ",division)
            pdfstitchbasedondivision(requestnumber, division)
            # pool.apply_async(pdfstitchbasedondivision, (requestnumber, division))
        
        # pool.close()
        # pool.join()
    except (Exception) as error:
        print('error with Thread Pool: ', error)
 
def pdfstitchbasedondivision(requestno, division):
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
                docbytes = getdocumentbytearray(producermessage)
                print("***************gets3documentbytearray******************")
                writer = mergepdf(docbytes, writer)
                count += 1
        if writer:
            print("*********************write to PDF**********************")
            savetos3(writer, requestno + division.get('division')+'.pdf', 'EDU-2022-12345', 'edu')          
    except(Exception) as error:
        print('error with item: ', error)

def getdocumentbytearray(message):
    # recordjobstart(message)
    try:
        docbytearray = gets3documentbytearray(message)
        # savedocumentdetails(message,dochashcode)
        # recordjobend(message, False)
        return docbytearray
    except(Exception) as error:
        # recordjobend(message, True, traceback.format_exc())
        print("error in getting the bytearray")
        raise

def uploadstitchedpdf(filename, bytesarray, requestnumber, bcgovcode):
    # recordjobstart(message)
    try:
        print("filename = ", filename)
        docobj = uploadbytes(filename, bytesarray, requestnumber, bcgovcode)
        # savedocumentdetails(message,dochashcode)
        # recordjobend(message, False)
        print(docobj)
        return docobj
    except(Exception) as error:
        # recordjobend(message, True, traceback.format_exc())
        print("error in writing the bytearray")
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
    
def savetos3(writer, filename, requestnumber, bcgovcode):
    with BytesIO() as bytes_stream:
        writer.write(bytes_stream)
        print("**************writer.write*****************") 
        bytes_stream.seek(0)
        uploadstitchedpdf(filename, bytes_stream, requestnumber, bcgovcode)