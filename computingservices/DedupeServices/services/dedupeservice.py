
from .s3documentservice import gets3documenthashcode
from .dedupedbservice import savedocumentdetails, recordjobstart, recordjobend, updateredactionstatus, pagecalculatorjobstart
from .documentspagecalculatorservice import documentspagecalculatorproducerservice
from models.pagecalculatorproducermessage import pagecalculatorproducermessage
import traceback


def processmessage(message):
    recordjobstart(message)
    try:
        hashcode, _pagecount = gets3documenthashcode(message)
        savedocumentdetails(message, hashcode, _pagecount)
        recordjobend(message, False)
        updateredactionstatus(message)
        _incompatible = True if str(message.incompatible).lower() == 'true' else False
        if not _incompatible:
            pagecalculatormessage = documentspagecalculatorproducerservice().createpagecalculatorproducermessage(message, _pagecount)
            pagecalculatorjobid = pagecalculatorjobstart(pagecalculatormessage)
            print("Pushed to Page Calculator Stream!!!")
            documentspagecalculatorproducerservice().producepagecalculatorevent(pagecalculatormessage, _pagecount, pagecalculatorjobid)
    except(Exception) as error:
        print("Exception while processing redis message, func processmessage(p3), Error : {0} ".format(error))
        recordjobend(message, True, error.args[0])