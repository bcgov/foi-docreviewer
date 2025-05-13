
from .s3documentservice import gets3documenthashcode
from .dedupedbservice import savedocumentdetails, recordjobstart, recordjobend, updateredactionstatus, pagecalculatorjobstart, compressionjobstart
from .documentspagecalculatorservice import documentspagecalculatorproducerservice
from models.pagecalculatorproducermessage import pagecalculatorproducermessage
from models.compressionproducermessage import compressionproducermessage
from .compressionproducerservice import compressionproducerservice
import traceback
from utils.basicutils import to_json


def processmessage(message):
    recordjobstart(message)
    try:
        hashcode, _pagecount = gets3documenthashcode(message)
        newdocumentid, is_created= savedocumentdetails(message, hashcode, _pagecount)
        print("Document created-",newdocumentid)
        recordjobend(message, False)
        #updateredactionstatus(message)
        _incompatible = True if str(message.incompatible).lower() == 'true' else False
        if not _incompatible:
            message.documentid= newdocumentid
            print("Message!!!",to_json(message))
            #compressionmessage =  compressionproducerservice().createcompressionproducermessage(message, _pagecount)
            compressionjobid = compressionjobstart(message)
            print("Pushed to Compression Stream!!!",compressionjobid)
            compressionproducerservice().producecompressionevent(message, compressionjobid)
        #if not _incompatible:
            pagecalculatormessage = documentspagecalculatorproducerservice().createpagecalculatorproducermessage(message, _pagecount)
            pagecalculatorjobid = pagecalculatorjobstart(pagecalculatormessage)
            print("Pushed to Page Calculator Stream!!!")
            documentspagecalculatorproducerservice().producepagecalculatorevent(pagecalculatormessage, _pagecount, pagecalculatorjobid)
    except(Exception) as error:
        print("Exception while processing redis message, func processmessage(p3), Error : {0} ".format(error))
        recordjobend(message, True, error.args[0])