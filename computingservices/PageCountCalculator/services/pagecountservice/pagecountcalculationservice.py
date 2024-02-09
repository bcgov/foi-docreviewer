
import traceback
import json
from .pagecountservice import pagecountservice
from services.dal.pagecount.documentservice import documentservice

class pagecountcalculationservice():

    def processmessage(self, message):
        try:
            documentservice().pagecalculatorjobstart(message)
            pagecountjson = pagecountservice().calculatepagecount(message)
            documentservice().pagecalculatorjobend(message, False, pagecountjson)
        except (Exception) as error:
            print('error occured in pagecount calculation service: ', error)
            documentservice().pagecalculatorjobend(message, True, pagecount="", message=format(error))