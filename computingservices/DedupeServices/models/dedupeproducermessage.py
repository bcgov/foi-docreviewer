class dedupeproducermessage(object):
    def __init__(self,s3filepath,bcgovcode,requestnumber,filename,ministryrequestid,attributes) -> None:
        self.s3filepath = s3filepath
        self.bcgovcode=bcgovcode
        self.requestnumber = requestnumber
        self.filename=filename
        self.ministryrequestid=ministryrequestid
        self.attributes=attributes