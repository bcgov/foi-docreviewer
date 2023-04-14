
from .s3documentservice import getcredentialsbybcgovcode
from utils import add_spacing_around_special_character
from commons import add_numbering_to_pdf, getimagepdf, convertimagetopdf
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
import logging

class pdfstitchservice(basestitchservice):

    def ispdfstitchjobcompleted(self, jobid, category):
        complete, err, attributes = ispdfstichjobcompleted(jobid, category)
        total_skippedfilecount, skippedfiles = basestitchservice().getskippedfiledetails(attributes)
        return complete, err, total_skippedfilecount, skippedfiles

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
                
                logging.info("division = %s", division.divisionname)
                result = pool.apply_async(self.pdfstitchbasedondivision, (requestnumber, division, s3credentials, bcgovcode, category)).get()
                results.append(result)
            pool.close()
            pool.join()
            finalmessage = self.__getfinalmessage(_message, results)            
            result = self.createfinaldocument(finalmessage, s3credentials)
            if result.get("success") == True:
                logging.info("final document path = %s", result.get("documentpath"))
                savefinaldocumentpath(result, _message.ministryrequestid, _message.category, _message.createdby)
                recordjobend(_message, False, finalmessage=finalmessage)
            else:
                errormessage = "Error in uploading the final document %s", result.get("filename")
                logging.error(errormessage)
                recordjobend(_message, True, finalmessage=finalmessage, message=errormessage) 
        except (Exception) as error:
            print('error with Thread Pool: ', error)
            print("trace >>>>>>>>>>>>>>>>>>>>> ", traceback.format_exc())
            finalmessage = self.__getfinalmessage(_message)
            recordjobend(_message, True, finalmessage=finalmessage, message=traceback.format_exc())
    
    def pdfstitchbasedondivision(self, requestno, division, s3credentials, bcgovcode, category):
        stitchedfiles = []
        stichedfilecount = 0
        skippedfiles = []
        skippedfilecount = 0
        
        count = 0
        writer = PdfWriter()

        try: 
            # process each file in divisional files           
            for file in division.files:
                # logging.info("filename = %s", file.filename)
                print("filename = ", file.filename)
                if count < len(division.files):
                    _, extension = path.splitext(file.s3uripath)
                    # stitch only ['.pdf','.png','.jpg']
                    extension = extension.lower()
                    if extension in ['.pdf','.png','.jpg']:
                        try:
                            docbytes = basestitchservice().getdocumentbytearray(file, s3credentials)
                            writer = self.mergepdf(docbytes, writer, extension, file.filename)
                            stitchedfiles.append(file.filename)
                            stichedfilecount += 1
                        except ValueError as value_error:
                            errorfilename, errormessage = value_error.args
                            logging.error(errormessage)
                            print("errorfilename = ", errorfilename)
                            skippedfiles.append(errorfilename)
                            skippedfilecount += 1
                            continue
                    count += 1
            if writer:
                with BytesIO() as bytes_stream:
                    writer.write(bytes_stream)
                    bytes_stream.seek(0)
                    paginationtext = add_spacing_around_special_character("-",requestno) + " | page [x] of [totalpages]"
                    numberedpdfbytes = add_numbering_to_pdf(bytes_stream, paginationtext=paginationtext)
                    filename = requestno + " - " +category+" - "+ division.divisionname
                    stitchedoutput = self.__getdivisionstitchoutput(division.divisionname, stitchedfiles, stichedfilecount, skippedfiles, skippedfilecount)
                    filestozip = basestitchservice().uploaddivionalfiles(filename,requestno, bcgovcode, s3credentials, numberedpdfbytes, division.files, division.divisionname)
                    return self.__getfinaldivisionoutput(stitchedoutput, filestozip)
        except ValueError as value_error:
            errorattribute, errormessage = value_error.args
            logging.error(errormessage)
        except(Exception) as error:
            logging.error('Error with divisional stitch.')
            logging.error(error)
            raise

    def mergepdf(self, raw_bytes_data, writer, extension, filename = None):
        try:
            if extension in ['.png','.jpg']:
                # process the image bytes
                reader =  convertimagetopdf(raw_bytes_data)
            else:
                reader = PdfReader(BytesIO(raw_bytes_data))
            
            # Add all pages to the writer
            for page in reader.pages:
                writer.add_page(page)
            return writer
        except(Exception) as error:
            raise ValueError(filename, error)
    
    def createfinaldocument(self, _message, s3credentials):
        if _message is not None:
            return basestitchservice().zipfilesandupload(_message, s3credentials)
    
    def __getfinaldivisionoutput(self, stitchedoutput, filestozip):
        formattedfilestozip = self.__formatfilestozip(filestozip)
        return {
            "stitchedoutput": stitchedoutput,
            "filestozip": formattedfilestozip
        }
    def __getdivisionstitchoutput(self, divisionname, stitchedfiles, stichedfilecount, skippedfiles, skippedfilecount):
        return {
            "divisionname": divisionname,
            "stitchedfiles": stitchedfiles,
            "stichedfilecount": stichedfilecount,
            "skippedfiles": skippedfiles,
            "skippedfilecount": skippedfilecount
        }

    def __formatfilestozip(self, filestozip):
        documents = []
        if filestozip:
            for file in filestozip:
                if file is not None:
                    document = {
                        "recordid": -1,
                        "filename": file.get("filename"),
                        "s3uripath": file.get("documentpath"),
                        "lastmodified": datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]
                    }
                    documents.append(document)
        return documents
    def __getfinalmessage(self, _message, results=None):
        stitchedoutput = []
        filestozip = []
        
        if results:
            print("__getfinalmessage results == ", results)
            for result in results:
                if result is not None:
                    stitchedoutput.append(result.get("stitchedoutput"))
                    filestozip += result.get("filestozip")
        finaloutput = {
            "stitchedoutput": stitchedoutput,
            "filestozip": filestozip
        }
        setattr(_message, "finaloutput", finaloutput)
        setattr(_message, "outputdocumentpath", filestozip)
        return _message



