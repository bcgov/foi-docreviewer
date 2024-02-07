class pagecalculatorproducermessage(object):
    def __init__(self,jobid,filename,pagecount,ministryrequestid,documentmasterid,trigger,createdby) -> None:
        self.jobid = jobid
        self.filename = filename
        self.pagecount = pagecount
        self.ministryrequestid = ministryrequestid        
        self.documentmasterid = documentmasterid
        self.trigger = trigger
        self.createdby = createdby
        