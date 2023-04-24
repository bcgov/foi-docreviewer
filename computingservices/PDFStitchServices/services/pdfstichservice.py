
from .s3documentservice import getcredentialsbybcgovcode
from utils import add_spacing_around_special_character
from commons import add_numbering_to_pdf, convertimagetopdf
import traceback
from io import BytesIO
from multiprocessing.pool import ThreadPool as Pool
from config import numbering_enabled, zip_enabled
from os import path
from .basestitchservice import basestitchservice
from .pdfstitchjob import recordjobstart, recordjobend, savefinaldocumentpath, ispdfstichjobcompleted
from datetime import datetime
import logging
import fitz

class pdfstitchservice(basestitchservice):

    def ispdfstitchjobcompleted(self, jobid, category):
        complete, err, attributes = ispdfstichjobcompleted(jobid, category)
        total_skippedfilecount, skippedfiles = basestitchservice().getskippedfiledetails(attributes)
        return complete, err, total_skippedfilecount, skippedfiles

    def processmessage(self, _message):        
        result = None
        try:
            recordjobstart(_message)
            s3credentials = getcredentialsbybcgovcode(_message.bcgovcode)
            # with Pool(len(attributes)) as pool:
            
                # loop through the atributes (currently divisions)
            results = [self.pdfstitchbasedondivision(_message.requestnumber, s3credentials, _message.bcgovcode, _message.category.capitalize(), division) for division in _message.attributes]
            print("stitching and divisional file upload completed")
                # results = [pool.apply_async(self.pdfstitchbasedondivision, (requestnumber, s3credentials, bcgovcode, category, division)).get() for division in attributes]
            finalmessage = self.__getfinalmessage(_message, results)
            # if zip_enabled == "True":
            print("Zipping final file")
            result = self.createfinaldocument(finalmessage, s3credentials)
            # else:
            #     result = {"success": True, "filename": "filename", "documentpath": "s3uri"}
            if result.get("success"):
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
        finally:
            result = None  

    def pdfstitchbasedondivision(self, requestnumber, s3credentials, bcgovcode, category, division):
        stitchedfiles = skippedfiles = []
        try: 
            writer = fitz.Document()
            
            # process each file in divisional files           
            for file in division.files:
            # logging.info("filename = %s", file.filename)
                print("filename = ", file.filename)
                _, extension = path.splitext(file.s3uripath)
                # stitch only ['.pdf','.png','.jpg']
                if extension.lower() in ['.pdf','.png','.jpg']:
                    try:
                        _bytes = self.getpdfbytes(extension.lower(), file, s3credentials)
                        with fitz.open(stream=BytesIO(_bytes)) as pdf_doc:
                            for page_num, page in enumerate(pdf_doc):
                                writer.insert_pdf(pdf_doc, from_page=page_num, to_page=page_num)
                        pdf_doc = _bytes = None
                        stitchedfiles.append(file.filename)
                    except Exception as exp:
                        logging.error(exp)
                        print("errorfilename = ", file.filename)
                        skippedfiles.append(file.filename)
                        continue
            
            with BytesIO() as bytes_stream:
                writer.save(bytes_stream)
                if writer:
                    writer.close()
                    writer = None                   
                bytes_stream.seek(0)

                filename = f"{requestnumber} - {category} - {division.divisionname}"
                if numbering_enabled == "True":
                    paginationtext = add_spacing_around_special_character("-",requestnumber) + " | page [x] of [totalpages]"
                    print("Numbering of stitched PDF")
                    numberedpdfbytes = add_numbering_to_pdf(bytes_stream.getvalue(), paginationtext=paginationtext)
                    print("Before uploaddivionalfiles")
                    filestozip = basestitchservice().uploaddivionalfiles(filename,requestnumber, bcgovcode, s3credentials, numberedpdfbytes, division.files, division.divisionname)
                    numberedpdfbytes = None
                else:
                    filestozip = basestitchservice().uploaddivionalfiles(filename,requestnumber, bcgovcode, s3credentials, bytes_stream, division.files, division.divisionname)
                return self.__getfinaldivisionoutput(
                self.__getdivisionstitchoutput(division.divisionname, stitchedfiles, len(stitchedfiles), skippedfiles, len(skippedfiles)), filestozip)
        except ValueError as value_error:
            errorattribute, errormessage = value_error.args
            logging.error(errormessage)
        except(Exception) as error:
            logging.error('Error with divisional stitch.')
            logging.error(error)
            raise
        

    def getpdfbytes(self, extension, file, s3credentials):
        raw_bytes_data = _bytes = None        
        try:
            raw_bytes_data = basestitchservice().getdocumentbytearray(file, s3credentials)
            if extension in ['.png', '.jpg']:
                return convertimagetopdf(raw_bytes_data)
            return raw_bytes_data
        except Exception as e:
            print(f"Error merging {file.filename}:", e)
            raise ValueError(file.filename, e)
        
        
    
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
        for file in filter(None, filestozip):
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
        if not results:
            finaloutput = {"stitchedoutput": [], "filestozip": []}
        else:
            for result in filter(None, results):
                stitchedoutput.append(result.get("stitchedoutput"))
                filestozip.extend(result.get("filestozip"))            
            finaloutput = {"stitchedoutput": stitchedoutput, "filestozip": filestozip}        
        _message.finaloutput = finaloutput
        _message.outputdocumentpath = filestozip        
        return _message