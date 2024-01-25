
import traceback
import json
from services.dal.pdfstitchjobactivity import pdfstitchjobactivity
class redactionsummaryservice():

    def processmessage(self,message):
        try:
            pdfstitchjobactivity().recordjobstatus(message,3,"redactionsummarystarted")
            print(message)
        except (Exception) as error:
            print('error occured in redaction summary service: ', error)
    
    

