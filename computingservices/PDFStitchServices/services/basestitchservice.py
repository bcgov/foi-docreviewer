
from .s3documentservice import gets3documentbytearray, uploadbytes
from commons import  getimagepdf
from rstreamio.message.schemas.divisionpdfstitch  import get_in_divisionpdfmsg
import traceback
from pypdf import PdfReader, PdfWriter
from io import BytesIO
from multiprocessing.pool import ThreadPool as Pool
import json
from zipfile import ZipFile
from os import path
from utils.constants import S3_FOLDER_FOR_HARMS

class basestitchservice:

    def getdocumentbytearray(self, message, s3credentials):
        try:
            docbytearray = gets3documentbytearray(message, s3credentials)
            return docbytearray
        except(Exception) as error:
            print("error in getting the bytearray >> ",error)
            raise
    
    def zipfiles(self, filename, s3credentials, stitchedpdfstream, files):
        archive = BytesIO()

        with ZipFile(archive, 'w') as zip_archive:
            # zip stitched pdf first
            with zip_archive.open(filename+'.pdf', 'w') as archivefile:
                archivefile.write(stitchedpdfstream)
            # zip any non pdf files
            for file in files:
                _, extension = path.splitext(file.s3uripath)
                if extension not in ['.pdf','.png','jpg']:
                    with zip_archive.open(file.filename, 'w') as archivefile:
                        _message = json.dumps({str(key): str(value) for (key, value) in file.items()})
                        _message = _message.replace("b'","'").replace("'",'')
                        producermessage = get_in_divisionpdfmsg(_message)
                        archivefile.write(self.getdocumentbytearray(producermessage, s3credentials))

        return archive.getbuffer()
        
    def zipfilesandupload(self, filename, requestnumber, bcgovcode, s3credentials, stitchedpdfstream, files):
        try:            
            bytesarray = self.zipfiles(filename, s3credentials, stitchedpdfstream, files)
            filepath = S3_FOLDER_FOR_HARMS + "/"+filename+".zip"
            print("zipfilename = ", filepath)
            docobj = uploadbytes(filepath, bytesarray, requestnumber, bcgovcode, s3credentials)
            print(docobj)
            return docobj
        except(Exception) as error:
            print("error in writing the bytearray >> ", error)
            raise