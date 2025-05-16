from utils.foidedupeconfig import compressionredishost,compressionredispassword,compressionredisport,compressionstreamkey,health_check_interval
from walrus import Database
from models.compressionproducermessage import compressionproducermessage
from utils.basicutils import to_json

class compressionproducerservice:
    compressionredisdb = None
    compressionredisstream = None
    def __init__(self) -> None:
        print("compressionredisport:",compressionredisport)

        self.compressionredisdb = Database(host=str(compressionredishost), port=str(compressionredisport), db=0,password=str(compressionredispassword), 
                                           retry_on_timeout=True, health_check_interval=int(health_check_interval), socket_keepalive=True)
        print("compressionstreamkey:",compressionstreamkey)
        self.compressionredisstream = self.compressionredisdb.Stream(compressionstreamkey)

    def producecompressionevent(self, finalmessage, jobid):        
        try:
            _compressionrequest = self.createcompressionproducermessage(finalmessage, jobid=jobid)
            print("_compressionrequest:",to_json(_compressionrequest))
            _compressionredisstream = self.compressionredisstream                      
            if _compressionredisstream is not None:
                print("_compressionredisstream:", _compressionredisstream)
                #print("IS error here?", _compressionrequest.__dict__)
                # sanitized_data = {
                #     k: str(v) if v is not None else "" 
                #     for k, v in _compressionrequest.__dict__.items()
                # }
                # print("sanitized_data", sanitized_data)
                #print("oooooooooo",_compressionredisstream.range(count=10))

                #return _compressionredisstream.add(sanitized_data, id="*")
                return _compressionredisstream.add(_compressionrequest.__dict__,id="*")      
        except (Exception) as error:           
            print("!!",error)
            raise error
    
    def createcompressionproducermessage(self,message,  jobid = 0):
            return compressionproducermessage(jobid=jobid, message=message)

