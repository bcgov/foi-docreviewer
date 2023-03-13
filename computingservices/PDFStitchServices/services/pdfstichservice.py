
from .s3documentservice import gets3documentbytearray, uploadbytes, getcredentialsbybcgovcode
from utils import add_numbering_to_pdf
from . import jsonmessageparser
import traceback
from pypdf import PdfReader, PdfWriter
from io import BytesIO
from multiprocessing.pool import ThreadPool as Pool
import json
from zipfile import ZipFile
from os import path


def processmessage(_message):
    decoder = json.JSONDecoder()
    requestnumber = _message.requestnumber
    bcgovcode = _message.bcgovcode
    attributes = decoder.decode(_message.attributes)
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
                _, extension = path.splitext(file.get('s3filepath'))
                if extension in ['.pdf']:
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
            with BytesIO() as bytes_stream:
                writer.write(bytes_stream)
                bytes_stream.seek(0)
                paginationtext = requestno + "| page [x] of [totalpages]"
                numberedpdfbytes = add_numbering_to_pdf(bytes_stream, paginationtext=paginationtext)
                zipfiles(requestno + division.get('division'), 'EDU-2022-12345', bcgovcode, s3credentials, numberedpdfbytes, division.get('files'))
    except(Exception) as error:
        print('error with item: ', error)

def getdocumentbytearray(message, s3credentials):
    try:
        docbytearray = gets3documentbytearray(message, s3credentials)
        return docbytearray
    except(Exception) as error:
        print("error in getting the bytearray >> ",error)
        raise

def uploadzipfile(filename, bytesarray, requestnumber, bcgovcode, s3credentials):
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

def zipfiles(filename, requestnumber, bcgovcode, s3credentials, stitchedpdfstream, files):
    archive = BytesIO()

    with ZipFile(archive, 'w') as zip_archive:
        # zip stitched pdf first
        with zip_archive.open(filename+'.pdf', 'w') as archivefile:
            archivefile.write(stitchedpdfstream)
        # zip any non pdf files
        for file in files:
            _, extension = path.splitext(file.get('s3filepath'))
            if extension not in ['.pdf']:
                with zip_archive.open(file.get('filename'), 'w') as archivefile:
                    _message = json.dumps({str(key): str(value) for (key, value) in file.items()})
                    _message = _message.replace("b'","'").replace("'",'')
                    producermessage = jsonmessageparser.getpdfstitchfilesproducermessage(_message)
                    archivefile.write(getdocumentbytearray(producermessage, s3credentials))


    uploadzipfile(filename+'.zip', archive.getbuffer(), requestnumber, bcgovcode, s3credentials)