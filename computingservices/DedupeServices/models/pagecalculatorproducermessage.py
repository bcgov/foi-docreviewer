class pagecalculatorproducermessage(object):
    def __init__(self,filename,pagecount,ministryrequestid,documentmasterid,trigger) -> None:
        self.filename = filename
        self.pagecount = pagecount
        self.ministryrequestid = ministryrequestid        
        self.documentmasterid = documentmasterid
        self.trigger = trigger
        