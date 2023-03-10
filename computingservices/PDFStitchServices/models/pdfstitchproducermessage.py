class pdfstitchproducermessage(object):
    def __init__(self,requestnumber,attributes) -> None:
        self.requestnumber = requestnumber
        self.attributes=attributes


class pdfstitchfilesproducermessage(object):
    def __init__(self,s3filepath,filename) -> None:
        self.s3filepath = s3filepath
        self.filename=filename

