class dedupeproducermessage(object):
    def __init__(self,s3filepath,bcgovcode,requestnumber,filename,ministryrequestid,attributes,batch,jobid,documentmasterid,trigger,createdby,outputdocumentmasterid=None) -> None:
        self.s3filepath = s3filepath
        self.bcgovcode=bcgovcode
        self.requestnumber = requestnumber
        self.filename=filename
        self.ministryrequestid=ministryrequestid
        self.attributes=attributes
        self.batch=batch
        self.jobid=jobid
        self.documentmasterid=documentmasterid
        self.outputdocumentmasterid=outputdocumentmasterid
        self.trigger=trigger
        self.createdby=createdby
