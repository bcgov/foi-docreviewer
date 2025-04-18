
from .s3documentservice import getcredentialsbybcgovcode
from utils import add_spacing_around_special_character
from commons import add_numbering_to_pdf
import traceback
from pypdf import PdfReader, PdfWriter
from io import BytesIO
from multiprocessing.pool import ThreadPool as Pool
import json
from os import path
from basestitchservice import basestitchservice

class blobpdfstitchservice(basestitchservice):

    def processmessage(self,_message):
        requestnumber = _message.requestnumber
        bcgovcode = _message.bcgovcode
        attributes = _message.attributes
        s3credentials = getcredentialsbybcgovcode(bcgovcode)
        
        try:
            pool = Pool(len(attributes))
            # loop through the atributes (currently divisions)
            for division in attributes:
                print("division = ",division)
                # pdfstitchbasedondivision(requestnumber, division, s3credentials, bcgovcode)
                pool.apply_async(self.pdfstitchbasedondivision, (requestnumber, division, s3credentials, bcgovcode))
            
            pool.close()
            pool.join()
        except (Exception) as error:
            print('error with Thread Pool: ', error)
    
    def pdfstitchbasedondivision(self, requestno, division, s3credentials, bcgovcode):
        try:
            print("division files : ",division.files)
            count = 0
            writer = PdfWriter()
            for file in division.files:
                if count < len(division.files):
                    _, extension = path.splitext(file.s3filepath)
                    extension = extension.lower()
                    if extension in ['.pdf','.png','jpg']:
                        """
                        Placeholder to handle blob
                        """
                         
                        docbytes = basestitchservice().getdocumentbytearray(file, s3credentials)
                        writer = self.mergepdf(docbytes, writer, extension)
                    count += 1
            if writer:
                print("*********************write to PDF**********************")
                with BytesIO() as bytes_stream:
                    writer.write(bytes_stream)
                    bytes_stream.seek(0)
                    paginationtext = add_spacing_around_special_character("-",requestno) + " | page [x] of [totalpages]"
                    numberedpdfbytes = add_numbering_to_pdf(bytes_stream, paginationtext=paginationtext)
                    basestitchservice().zipfilesandupload(requestno + division.division, 'EDU-2022-12345', bcgovcode, s3credentials, numberedpdfbytes, division.files)
        except(Exception) as error:
            print('error with file: ', error)

    def mergepdf(self, raw_bytes_data, writer, extension):
        # if extension in ['.png','jpg']:
        #     # process the image bytes        
        #     reader =  getimagepdf(raw_bytes_data)
        # else:
        reader = PdfReader(BytesIO(raw_bytes_data))
        
        # Add all pages to the writer
        for page in reader.pages:
            print("**************Add Page*****************") 
            writer.add_page(page)
        return writer


