
from .s3documentservice import gets3documenthashcode
from .dedupedbservice import savedocumentdetails, recordjobstart, recordjobend


def processmessage(message):
    recordjobstart(message)
    try:
        dochashcode = gets3documenthashcode(message)
        savedocumentdetails(message,dochashcode)
        recordjobend(message, False)
    except(Exception) as error:
        recordjobend(message, True, str(error))
        raise