from config import zipperredishost,zipperredispassword,zipperredisport,zipperstreamkey,health_check_interval
from walrus import Database
from models.zipperproducer import zipperproducer
from utils.basicutils import to_json

class zipperproducerservice:
    zipperredisdb = None
    zipperredisstream = None
    def __init__(self) -> None:
        self.zipperredisdb = Database(host=str(zipperredishost), port=str(zipperredispassword), db=0,password=str(zipperredisport), retry_on_timeout=True, health_check_interval=int(health_check_interval), socket_keepalive=True)
        self.zipperredisstream = self.zipperredisdb.Stream(zipperstreamkey)

    def producezipevent(self,finalmessage):        
        try:
            _zipperrequest = zipperproducer(jobid=finalmessage.jobid,requestid=finalmessage.requestid,category=finalmessage.category,requestnumber=finalmessage.requestnumber,
                                            bcgovcode=finalmessage.bcgovcode,createdby=finalmessage.createdby,ministryrequestid=finalmessage.ministryrequestid,
                                            filestozip=to_json(finalmessage.outputdocumentpath),finaloutput=to_json(finalmessage.finaloutput),attributes=to_json(finalmessage.attributes),foldername=finalmessage.foldername)
            _zipperredisstream = self.zipperredisstream                      
            if _zipperredisstream is not None:
                return _zipperredisstream.add(_zipperrequest.__dict__,id="*")                    
        except (Exception) as error:           
            print(error)
            raise error                                     

