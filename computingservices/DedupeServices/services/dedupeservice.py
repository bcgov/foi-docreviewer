
from .s3documentservice import gets3documenthashcode
from .dedupedbservice import savedocumentdetails


def processmessage(message):   
    dochashcode = gets3documenthashcode(message)
    savedocumentdetails(message,dochashcode)