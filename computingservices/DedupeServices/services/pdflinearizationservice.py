from os import path
from io import BytesIO
import fitz
from utils import (
    file_conversion_types
)
from .s3documentservice import gets3documentbytearray, uploaddocument

class pdflinearizationservice:

    def linearizepdf(self, producermessage):
        try:        
            _filename, extension = path.splitext(producermessage.filename)
            s3uripath = ""
            if extension.lower() in [".pdf"] or extension.lower() in file_conversion_types:
                pdfbytearray = gets3documentbytearray(producermessage)            
                if pdfbytearray:
                    _bytes = BytesIO(pdfbytearray)
                    pdf_doc_in = fitz.open(stream=_bytes)
                bytes_stream = BytesIO()
                if pdf_doc_in:
                    pdf_doc_in.save(bytes_stream, linear=True)
                    s3uripath = path.splitext(producermessage.s3filepath)[0] + "_linearized" + extension
                    uploaddocument(producermessage.bcgovcode, s3uripath, bytes_stream.getvalue())
                    pdf_doc_in.close()
                    del pdf_doc_in
                    bytes_stream.close()
            return s3uripath
        except Exception as ex:
            print("Error in Linearizing PDF")
            print(ex)
            raise
