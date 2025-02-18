
from .s3documentservice import getcredentialsbybcgovcode
from utils import add_spacing_around_special_character
from commons import add_numbering_to_pdf, convertimagetopdf
import traceback
from io import BytesIO
from multiprocessing.pool import ThreadPool as Pool
from config import numbering_enabled
from os import path
from .basestitchservice import basestitchservice
from .pdfstitchjob import recordjobstart, recordjobend, savefinaldocumentpath, ispdfstichjobcompleted, ispdfstichjobstarted
from datetime import datetime
import logging
import fitz
from utils.basicutils import to_json
from .zipperproducerservice import zipperproducerservice as zipperservice
from config import division_stitch_folder_path

class pdfstitchservice(basestitchservice):

    def ispdfstitchjobstarted(self, jobid, category):
        return ispdfstichjobstarted(jobid, category)

    def ispdfstitchjobcompleted(self, jobid, category):
        total_skippedfilecount = 0
        skippedfiles = None
        complete, err, attributes = ispdfstichjobcompleted(jobid, category)
        if attributes:
            total_skippedfilecount, skippedfiles = basestitchservice().getskippedfiledetails(attributes)
        return complete, err, total_skippedfilecount, skippedfiles

    def processmessage(self, _message):        
        result = None
        results = []
        try:
            print(f"<<<< recordjobstart: {datetime.now()} >>>>")
            recordjobstart(_message)
            s3credentials = getcredentialsbybcgovcode(_message.bcgovcode)
            # with Pool(len(attributes)) as pool:
            
                # loop through the atributes (currently divisions)
            for division in _message.attributes:
                
                logging.info("division = %s", division.divisionname)
                
                result = self.pdfstitchbasedondivision(_message.requestnumber, s3credentials, _message.bcgovcode, _message.category.capitalize(), division)
                results.append(result)
                # results = [pool.apply_async(self.pdfstitchbasedondivision, (requestnumber, s3credentials, bcgovcode, category, division)).get() for division in attributes]
            finalmessage = self.__getfinalmessage(_message, results)
            print("<<< Starting  Zipping >>>>> ")            
            zipperservice().producezipevent(finalmessage)
            print("<<< Zipping event produced!!! over to Zipper Services >>>>> ")            
        except (Exception) as error:
            print("trace >>>>>>>>>>>>>>>>>>>>> ", traceback.format_exc())
            print(error)
            finalmessage = self.__getfinalmessage(_message)
            recordjobend(_message, True, finalmessage=finalmessage, message=traceback.format_exc())
            print(f"<<<< recordjobend Exception: {datetime.now()} >>>>")
        finally:
            result = None  
            

    def pdfstitchbasedondivision(self, requestnumber, s3credentials, bcgovcode, category, division):
        stitchedfiles = []
        skippedfiles = []
        try: 
            writer = fitz.open()
            
            # process each file in divisional files           
            for file in division.files:
                logging.info("filename = %s", file.filename)
                print(f"filename = {file.filename}")
                _, extension = path.splitext(file.s3uripath)
                # stitch only ['.pdf','.png','.jpg', '.jpeg']
                if extension.lower() in ['.pdf','.png','.jpg', '.jpeg']:
                    try:
                        _bytes = BytesIO(self.getpdfbytes(extension.lower(), file, s3credentials))
                        pdf_doc_in = fitz.open(stream=_bytes) #input PDF
                        if hasattr(file, 'rotatedpages'):
                            rotatedpages = file.rotatedpages.__dict__
                            for page in rotatedpages:
                                pdf_doc_in[int(page)-1].set_rotation(rotatedpages[page])
                        pdf_doc = fitz.open()  # output PDF
                        if pdf_doc_in.is_form_pdf is not False and pdf_doc_in.is_form_pdf > 0:  #check if form field exists, if so convert doc to series of page images & combine to 1 pdf
                            for page in pdf_doc_in:
                                if len(list(page.widgets())) > 0:
                                    w, h = page.rect.br  # page width / height taken from bottom right point coords
                                    outpage = pdf_doc.new_page(width=w, height=h)  # out page has same dimensions
                                    pix = page.get_pixmap(dpi=150)  # set desired resolution
                                    outpage.insert_image(page.rect, pixmap=pix)
                                else:
                                    pdf_doc.insert_pdf(pdf_doc_in, page.number, page.number)
                            #pdf_doc.save("Output.pdf", garbage=3, deflate=True)
                        else:
                            pdf_doc= pdf_doc_in
                        if pdf_doc.needs_pass:
                            raise ValueError("Password-protected PDF document")                            
                        else:
                            writer.insert_pdf(pdf_doc)
                        pdf_doc.close()
                        fitz.TOOLS.store_shrink(100)                    
                        _bytes.close()
                        del pdf_doc
                        del _bytes
                        
                        stitchedfiles.append(file.filename)
                    except Exception as exp:
                        logging.error(exp)
                        logging.info("errorfilename = %s", file.filename)
                        print(f"errorfilename = {file.filename}")
                        skippedfiles.append(file.filename)
                        continue
            
            bytes_stream = BytesIO()
            if writer:
                print(f"save stitched doc to the bytes_stream: {datetime.now()}")
                writer.save(bytes_stream)
                writer.close()
                fitz.TOOLS.store_shrink(100)
                del writer
                print(f"save stitched doc to the bytes_stream completed: {datetime.now()}")
                filename = f"{requestnumber} - {self.__getfolderfordivisionfiles()} - {division.divisionname}"
                    
                if numbering_enabled == "True":
                    paginationtext = add_spacing_around_special_character("-",requestnumber) + " | page [x] of [totalpages]"
                    print("<<<< Numbering started >>>>")
                    numberedpdfbytes = add_numbering_to_pdf(bytes_stream.getvalue(), paginationtext=paginationtext)
                    print("<<<< Numbering finished >>>>")
                    filestozip = basestitchservice().uploaddivionalfiles(filename,requestnumber, bcgovcode, s3credentials, numberedpdfbytes, division.files, division.divisionname)
                    filestozip = basestitchservice().getincompatablefilepaths(division.divisionname, division.files, filestozip)
                    numberedpdfbytes = None
                else:
                    filestozip = basestitchservice().uploaddivionalfiles(filename,requestnumber, bcgovcode, s3credentials, bytes_stream.getvalue(), division.files, division.divisionname)
                    filestozip = basestitchservice().getincompatablefilepaths(division.divisionname, division.files, filestozip)
                    
                bytes_stream.close()
                del bytes_stream
                return self.__getfinaldivisionoutput(filestozip,
                        self.__getdivisionstitchoutput(division.divisionname, stitchedfiles, len(stitchedfiles), skippedfiles, len(skippedfiles)))
            else:
                filestozip = basestitchservice().getincompatablefilepaths(division.divisionname, division.files)
                return self.__getfinaldivisionoutput(filestozip, None)
        except(Exception) as error:
            logging.error('Error with divisional stitch.')
            logging.error(error)
            raise
        

    def getpdfbytes(self, extension, file, s3credentials):
        raw_bytes_data = None        
        try:
            raw_bytes_data = basestitchservice().getdocumentbytearray(file, s3credentials)
            if extension in ['.png', '.jpg', '.jpeg']:
                return convertimagetopdf(raw_bytes_data)
            return raw_bytes_data
        except Exception as e:
            logging.error(f"Error merging {file.filename}: " + str(e))
            raise ValueError(file.filename, e)
        
        
    
    def createfinaldocument(self, _message, s3credentials):
        if _message is not None:
            return basestitchservice().zipfilesandupload(_message, s3credentials)
        return {"success": False, "filename": "", "documentpath": ""}
    
    def __getfinaldivisionoutput(self, filestozip, stitchedoutput):
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
        
        if results:
            for result in results:
                if result is not None:
                    if result.get("stitchedoutput"):
                        stitchedoutput.append(result.get("stitchedoutput"))
                    filestozip += result.get("filestozip")
        finaloutput = {
            "stitchedoutput": stitchedoutput,
            "filestozip": filestozip
        }
        setattr(_message, "foldername", self.__getfolderfordivisionfiles())        
        setattr(_message, "finaloutput", finaloutput)
        setattr(_message, "outputdocumentpath", filestozip)
        return _message
    
    def __getfolderfordivisionfiles(self):
        return division_stitch_folder_path.split("/")[0]
