
from .s3documentservice import gets3documenthashcode
from .dedupedbservice import savedocumentdetails, recordjobstart, recordjobend, updateredactionstatus
from .pdflinearizationservice import pdflinearizationservice
import traceback


def processmessage(message):
    recordjobstart(message)
    try:
        hashcode, _pagecount = gets3documenthashcode(message)
        linearizedfilepath = pdflinearizationservice().linearizepdf(message)
        print(f'linearizedfilepath = {linearizedfilepath}')
        savedocumentdetails(message, hashcode, _pagecount, linearizedfilepath)     
        recordjobend(message, False)
        updateredactionstatus(message)
    except(Exception) as error:
        print("Exception while processing redis message, func processmessage(p3), Error : {0} ".format(error))
        recordjobend(message, True, traceback.format_exc())