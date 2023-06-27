

class zipperproducer(object):

    def __init__(self,requestid,category,requestnumber,bcgovcode,createdby,ministryrequestid,filestozip) -> None:
        self.requestid = requestid
        self.category=category
        self.requestnumber = requestnumber
        self.bcgovcode = bcgovcode
        self.createdby = createdby
        self.ministryrequestid = ministryrequestid
        self.filestozip = filestozip
