
from .s3documentservice import gets3documentbytearray, uploadbytes
from commons import  getimagepdf
from rstreamio.message.schemas.divisionpdfstitch  import get_in_filepdfmsg
import traceback
from pypdf import PdfReader, PdfWriter
from io import BytesIO
from multiprocessing.pool import ThreadPool as Pool
import json
from zipfile import ZipFile
from os import path
from utils.constants import S3_FOLDER_FOR_HARMS
from utils.basicutils import to_json

class basestitchservice:

    def getdocumentbytearray(self, message, s3credentials):
        try:
            docbytearray = gets3documentbytearray(message, s3credentials)
            return docbytearray
        except(Exception) as error:
            print("error in getting the bytearray >> ",error)
            raise
    
    def __zipfiles(self, filename, s3credentials, stitchedpdfstream, files):
        archive = BytesIO()

        with ZipFile(archive, 'w') as zip_archive:
            # zip stitched pdf first
            if stitchedpdfstream is not None:
                with zip_archive.open(filename+'.pdf', 'w') as archivefile:
                    archivefile.write(stitchedpdfstream)
            # zip any non pdf files
            for file in files:
                print("file Obj >>>>>>>> ",to_json(file))
                _message = to_json(file)
                producermessage = get_in_filepdfmsg(_message)
                _, extension = path.splitext(producermessage.s3uripath)
                if extension not in ['.pdf','.png','jpg']:
                    with zip_archive.open(producermessage.filename, 'w') as archivefile:                        
                        # _message = json.dumps({str(key): str(value) for (key, value) in file.items()})
                        # _message = _message.replace("b'","'").replace("'",'')
                        # _message = to_json(file)
                        # producermessage = get_in_filepdfmsg(_message)
                        print("fileproducermessage.s3uripath >>>>>>>> ", producermessage.s3uripath)
                        archivefile.write(self.getdocumentbytearray(producermessage, s3credentials))

        return archive.getbuffer()
    
    def zipfiles(self, s3credentials, files):
        archive = BytesIO()

        with ZipFile(archive, 'w') as zip_archive:           
            # zip final folders/files
            for file in files:
                _message = to_json(file)
                producermessage = get_in_filepdfmsg(_message)
                with zip_archive.open(producermessage.filename, 'w') as archivefile:
                    archivefile.write(self.getdocumentbytearray(producermessage, s3credentials))
        return archive.getbuffer()
        
    def zipfilesandupload(self, filename, requestnumber, bcgovcode, s3credentials, files):
        try:            
            bytesarray = self.zipfiles(s3credentials, files)
            filepath = S3_FOLDER_FOR_HARMS + "/"+filename+".zip"
            print("zipfilename = ", filepath)
            docobj = uploadbytes(filepath, bytesarray, requestnumber, bcgovcode, s3credentials)
            print(docobj)
            return docobj
        except(Exception) as error:
            print("error in writing the bytearray >> ", error)
            raise
    
    def uploaddivionalfiles(self, filename, requestnumber, bcgovcode, s3credentials, stitchedpdfstream, files, divisionname):
        try:
            folderpath = S3_FOLDER_FOR_HARMS + "/"+ divisionname 
            filepath = folderpath + "/" +filename+".pdf"
            docobjs = []
            docobj = uploadbytes(filepath, stitchedpdfstream, requestnumber, bcgovcode, s3credentials)
            docobjs.append(docobj)
            for file in files:
                _jsonfile = to_json(file)
                _file = get_in_filepdfmsg(_jsonfile)
                _, extension = path.splitext(_file.s3uripath)
                if extension not in ['.pdf','.png','jpg']:
                    incompatabledocobj = self.__saveincompatablefiles(_file, s3credentials, requestnumber, bcgovcode, folderpath)
                    docobjs.append(incompatabledocobj)
            print(docobjs)
            return docobjs
        except(Exception) as error:
            print("error in writing the bytearray >> ", error)
            raise
    
    def __saveincompatablefiles(self, _file, s3credentials, requestnumber, bcgovcode, folderpath):
        _bytearray = self.getdocumentbytearray(_file, s3credentials)
        filepath = folderpath + "/"+_file.filename
        return uploadbytes(filepath, _bytearray, requestnumber, bcgovcode, s3credentials)