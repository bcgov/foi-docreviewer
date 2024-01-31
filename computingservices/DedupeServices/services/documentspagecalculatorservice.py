from utils.foidedupeconfig import pagecalculatorredishost,pagecalculatorredispassword,pagecalculatorredisport,pagecalculatorstreamkey,health_check_interval
from walrus import Database
from models.pagecalculatorproducermessage import pagecalculatorproducermessage
from utils.basicutils import to_json

class documentspagecalculatorproducerservice:
    pagecalculatorredisdb = None
    pagecalculatorredisstream = None
    def __init__(self) -> None:
        self.pagecalculatorredisdb = Database(host=str(pagecalculatorredishost), port=str(pagecalculatorredisport), db=0,password=str(pagecalculatorredispassword), retry_on_timeout=True, health_check_interval=int(health_check_interval), socket_keepalive=True)
        self.pagecalculatorredisstream = self.pagecalculatorredisdb.Stream(pagecalculatorstreamkey)

    def producepagecalculatorevent(self,finalmessage, pagecount):        
        try:
            _pagecalculatorrequest = pagecalculatorproducermessage(filename=finalmessage.filename, pagecount=pagecount, 
                                    ministryrequestid=finalmessage.ministryrequestid, documentmasterid=finalmessage.documentmasterid,
                                    trigger=finalmessage.trigger)
            _pagecalculatorredisstream = self.pagecalculatorredisstream                      
            if _pagecalculatorredisstream is not None:
                return _pagecalculatorredisstream.add(_pagecalculatorrequest.__dict__,id="*")                    
        except (Exception) as error:           
            print(error)
            raise error

