class zipperproducermessage(object):
    def __init__(self,jobid,requestid,category,requestnumber,bcgovcode,createdby,ministryrequestid,filestozip,finaloutput,attributes,foldername) -> None:
        self.jobid = jobid
        self.requestid = requestid
        self.category=category
        self.requestnumber = requestnumber
        self.bcgovcode = bcgovcode
        self.createdby = createdby
        self.ministryrequestid = ministryrequestid
        self.filestozip = filestozip
        self.finaloutput = finaloutput
        self.attributes = attributes
        self.foldername = foldername
