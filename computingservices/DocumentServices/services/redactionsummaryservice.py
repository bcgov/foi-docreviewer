
import traceback
import json
from services.dal.pdfstitchjobactivity import pdfstitchjobactivity
from services.dts.redactionsummary import redactionsummary
class redactionsummaryservice():

    def processmessage(self,message):
        try:
            pdfstitchjobactivity().recordjobstatus(message,3,"redactionsummarystarted")
            #Get Data ; Begin
            divisiondocuments = json.loads(message.summarydocuments)
            for entry in divisiondocuments:
                divisionid = entry['divisionid']
                documentids = entry['documentids']
                formattedsummary = redactionsummary().prepareredactionsummary(message, documentids)
            #Get Data : End
            #Get Template
            #Document
            #Upload to S3
            #Invoke ZIP
            
            #print(message)
                print(formattedsummary)
        except (Exception) as error:
            print('error occured in redaction summary service: ', error)

   
    

