
import traceback
import json
from services.dal.pdfstitchjobactivity import pdfstitchjobactivity
from services.dts.redactionsummary import redactionsummary
class redactionsummaryservice():

    def processmessage(self,message):
        try:
            pdfstitchjobactivity().recordjobstatus(message,3,"redactionsummarystarted")
            #Get Data ; Begin
            formattedsummary = redactionsummary().prepareredactionsummary(message)
            #Get Data : End
            #Get Template
            #Document
            #Upload to S3
            #Invoke ZIP
            print(message)
        except (Exception) as error:
            print('error occured in redaction summary service: ', error)
    
    

