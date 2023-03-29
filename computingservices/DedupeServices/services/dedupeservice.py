
from .s3documentservice import gets3documenthashcode
from .dedupedbservice import savedocumentdetails, recordjobstart, recordjobend, updateredactionstatus
import traceback


def processmessage(message):
    recordjobstart(message)
    try:
        resultdochashcode_pagecount = gets3documenthashcode(message)
        savedocumentdetails(message,resultdochashcode_pagecount[0],resultdochashcode_pagecount[1])
        recordjobend(message, False)
        updateredactionstatus(message)
    except(Exception) as error:
        recordjobend(message, True, traceback.format_exc())
        raise