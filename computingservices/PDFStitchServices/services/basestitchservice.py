
from .s3documentservice import gets3documentbytearray, uploadbytes
from rstreamio.message.schemas.divisionpdfstitch  import get_in_filepdfmsg
from io import BytesIO
from zipfile import ZipFile
import zipfile
from os import path
from utils.basicutils import to_json
from config import division_stitch_folder_path, zip_enabled
import logging
import gc

class basestitchservice:
    def getdocumentbytearray(self, message, s3credentials):
        try:
            return gets3documentbytearray(message, s3credentials)
        except(Exception) as error:
            logging.error(error)
            raise ValueError(message.filename, error)
    
        
    def zipfiles(self, s3credentials, files):
        archive = BytesIO()

        with ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zip_archive:           
            # zip final folders/files
            for file in files:
                _message = to_json(file)
                producermessage = get_in_filepdfmsg(_message)
                with zip_archive.open(producermessage.filename, 'w') as archivefile:
                    archivefile.write(self.getdocumentbytearray(producermessage, s3credentials))
        return archive.getbuffer()
        
    def zipfilesandupload(self, _message, s3credentials):
        requestnumber = _message.requestnumber
        bcgovcode = _message.bcgovcode
        files = _message.outputdocumentpath
        category = _message.category
        try:            
            bytesarray = self.zipfiles(s3credentials, files)
            filepath = self.__getzipfilepath(category, requestnumber)
            logging.info("zipfilename = %s", filepath)
            docobj = uploadbytes(filepath, bytesarray, requestnumber, bcgovcode, s3credentials)
            return docobj
        except(ValueError) as error:
            errorattachmentobj, errormessage = error.args
            logging.error(errormessage)
            return errorattachmentobj
        except(Exception) as ex:
            logging.error("error in writing the bytearray")
            logging.error(ex)
            raise
    
    def uploaddivionalfiles(self, filename, requestnumber, bcgovcode, s3credentials, filebytes, files, divisionname):
        docobjs = []
        try:
            folderpath = self.__getfolderpathfordivisionfiles(divisionname)
            filepath = folderpath + "/" +filename+".pdf"
            if zip_enabled == "True":
                print("uploading divisional files to s3, filepath: ", filepath)
                docobj = uploadbytes(filepath, filebytes, requestnumber, bcgovcode, s3credentials)
                print("uploaded divisional files to s3, filepath: ", filepath)
                docobjs.append(docobj)
            for file in files:
                _jsonfile = to_json(file)
                _file = get_in_filepdfmsg(_jsonfile)
                _, extension = path.splitext(_file.s3uripath)
                if extension.lower() not in ['.pdf','.png','.jpg']:
                    incompatabledocobj = self.__getincompatablefiles(_file, divisionname)
                    docobjs.append(incompatabledocobj)
            return docobjs
        except(ValueError) as error:
            errorattachmentobj, errormessage = error.args
            logging.error(errormessage)
            raise
        except(Exception) as ex:
            logging.error("error in writing the bytearray")
            logging.error(ex)
            raise

    def getskippedfiledetails(self, data):
        total_skippedfilecount = 0
        total_skippedfiles = []

        for output in data['stitchedoutput']:
            skippedfilecount = output['skippedfilecount']
            skippedfiles = output['skippedfiles']
            total_skippedfilecount += skippedfilecount
            total_skippedfiles.extend(skippedfiles)
        
        total_skippedfiles = list(set(total_skippedfiles))
        return total_skippedfilecount, total_skippedfiles
    
    def __getincompatablefiles(self, _file, divisionname):
        folderpath = self.__getfolderpathfordivisionfiles(divisionname)
        filename = folderpath + "/" + _file.filename
        incompatablefiledetails = {"success": True, "filename": filename, "documentpath": _file.s3uripath}
        return incompatablefiledetails
    
    def __getfolderpathfordivisionfiles(self, divisionname):
        return division_stitch_folder_path.replace("divisionname", divisionname)
    
    def __getzipfilepath(self, category, filename):
        return category.capitalize() + "/"+filename+".zip" if category is not None else filename+".zip"