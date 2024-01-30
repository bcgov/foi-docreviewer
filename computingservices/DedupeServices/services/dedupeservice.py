
from .s3documentservice import gets3documenthashcode
from .dedupedbservice import savedocumentdetails, recordjobstart, recordjobend, updateredactionstatus
from .documentspagecalculatorservice import documentspagecalculatorproducerservice
import traceback


def processmessage(message):
    recordjobstart(message)
    try:
        hashcode, _pagecount = gets3documenthashcode(message)
        savedocumentdetails(message, hashcode, _pagecount)
        recordjobend(message, False)
        updateredactionstatus(message)
        documentspagecalculatorproducerservice().producepagecalculatorevent(message)
    except(Exception) as error:
        print("Exception while processing redis message, func processmessage(p3), Error : {0} ".format(error))
        recordjobend(message, True, traceback.format_exc())