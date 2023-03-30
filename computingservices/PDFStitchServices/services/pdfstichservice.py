
from .s3documentservice import getcredentialsbybcgovcode
from utils import add_spacing_around_special_character
from commons import add_numbering_to_pdf, getimagepdf
from rstreamio.message.schemas.divisionpdfstitch  import get_in_filepdfmsg
import traceback
from pypdf import PdfReader, PdfWriter
from io import BytesIO
from multiprocessing.pool import ThreadPool as Pool
import json
from os import path
from .basestitchservice import basestitchservice
from .pdfstitchjob import recordjobstart, recordjobend, savefinaldocumentpath, ispdfstichjobcompleted
from datetime import datetime

class pdfstitchservice(basestitchservice):

    def ispdfstitchjobcompleted(self, jobid, category):
        return ispdfstichjobcompleted(jobid, category)

    def processmessage(self,_message):
        recordjobstart(_message)
        requestnumber = _message.requestnumber
        bcgovcode = _message.bcgovcode
        attributes = _message.attributes
        s3credentials = getcredentialsbybcgovcode(bcgovcode)
        category = _message.category.capitalize()
        
        try:
            results = []
            pool = Pool(len(attributes))
            
            # loop through the atributes (currently divisions)
            for division in attributes:
                
                print("division = ",division.divisionname)
                result = pool.apply_async(self.pdfstitchbasedondivision, (requestnumber, division, s3credentials, bcgovcode, category)).get()
                results = results + result
            pool.close()
            pool.join()
            finalmessage = self.__getmessageforrecordjobend(_message, results)            
            result = self.createfinaldocument(finalmessage, s3credentials)
            if result.get("success") == True:
                print("final document path =========== ", result.get("documentpath"))
                savefinaldocumentpath(result, _message.ministryrequestid, _message.category, _message.createdby)
                recordjobend(_message, False, finalmessage=finalmessage)
        except (Exception) as error:
            print('error with Thread Pool: ', error)
            print("trace >>>>>>>>>>>>>>>>>>>>> ", traceback.format_exc())
            recordjobend(_message, True, finalmessage=finalmessage, message=traceback.format_exc())
    
    def pdfstitchbasedondivision(self, requestno, division, s3credentials, bcgovcode, category):
        try:
            count = 0
            writer = PdfWriter()
            for file in division.files:
                print("filename = ", file.filename)
                if count < len(division.files):
                    _, extension = path.splitext(file.s3uripath)
                    if extension in ['.pdf','.png','.jpg']:
                        docbytes = basestitchservice().getdocumentbytearray(file, s3credentials)
                        writer = self.mergepdf(docbytes, writer, extension)
                    count += 1
            if writer:
                with BytesIO() as bytes_stream:
                    writer.write(bytes_stream)
                    bytes_stream.seek(0)
                    paginationtext = add_spacing_around_special_character("-",requestno) + " | page [x] of [totalpages]"
                    numberedpdfbytes = add_numbering_to_pdf(bytes_stream, paginationtext=paginationtext)
                    filename = requestno + " - " +category+" - "+ division.divisionname
                    return basestitchservice().uploaddivionalfiles(filename,requestno, bcgovcode, s3credentials, numberedpdfbytes, division.files, division.divisionname)
        except(Exception) as error:
            print('error with file: ', error)

    def mergepdf(self, raw_bytes_data, writer, extension):
        if extension in ['.png','.jpg']:
            # process the image bytes  
            reader =  getimagepdf(raw_bytes_data)
        else:
            reader = PdfReader(BytesIO(raw_bytes_data))
        
        # Add all pages to the writer
        for page in reader.pages:
            writer.add_page(page)
        return writer
    def createfinaldocument(self, _message, s3credentials):
        print("<<<<<<<<<<<<<<<<<<<<< createfinaldocument >>>>>>>>>>>>>>>>>>>>>")
        if _message is not None:
            return basestitchservice().zipfilesandupload(_message, s3credentials)
    
    def __getmessageforrecordjobend(self, _message, results):
        documents = []
        for result in results:
            if result is not None:
                document = {
                    "recordid": -1,
                    "filename": result.get("filename"),
                    "s3uripath": result.get("documentpath"),
                    "lastmodified": datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]
                }
                documents.append(document)
        setattr(_message, "outputdocumentpath", documents)
        return _message



