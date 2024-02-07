
import traceback
import json
from services.dal.pdfstitchjobactivity import pdfstitchjobactivity
from .documentgenerationservice import documentgenerationservice
from .s3documentservice import uploadbytes
from services.dts.redactionsummary import redactionsummary
class redactionsummaryservice():

    def processmessage(self,message):
        try:
            print("***BEFORE CALL TO pdfstitchjobactivity!!")
            pdfstitchjobactivity().recordjobstatus(message,3,"redactionsummarystarted")
            print("***message:",message)
            #TODO : For each division generate the pdf & upload to respective folders!!
            print("***Before calling generate_pdf -messageattributes:", json.dumps(message.attributes))
            category = message.category
            documenttypename= category+"_redaction_summary"
            print("***documenttypename:",documenttypename)
            print("#######1",json.loads(message.attributes)[0])     
            #receipt_template_path= r'templates/redline_redaction_summary.docx'
            #Get Data ; Begin
            divisiondocuments = json.loads(message.summarydocuments)
            print("***divisiondocuments:",divisiondocuments)
            upload_responses=[]
            for entry in divisiondocuments:
                divisionid = entry['divisionid']
                documentids = entry['documentids']
                formattedsummary = redactionsummary().prepareredactionsummary(message, documentids)
                print("\n***Formattedsummary - {} : {}",divisionid,formattedsummary)
                #Get Data : End
                #Get Template
                redline_redaction_summary= documentgenerationservice().generate_pdf(documenttypename,formattedsummary)
                print("\nFinished generate_pdf!!")
                #Method for calling the pdf generation method ends
                #Document
                #Upload to S3 starts
                messageattributes= json.loads(message.attributes)         
                s3uri = messageattributes[0]['files'][0]['s3uripath']
                # Find the last occurrence of '/'
                last_slash_index = s3uri.rfind('/')
                print("***Updated last_slash_index",last_slash_index)
                # Remove the filename and everything after it
                s3uri = s3uri[:last_slash_index + 1]
                print("***Updated URI",s3uri)
                divisionname = messageattributes[0]['divisionname']
                #"redline" #get it from message
                requestnumber=formattedsummary["requestnumber"]
                filename = f"{requestnumber} - {category} - {divisionname} - summary"
                print("\nBefore calling uploadbytes", s3uri )
                uploadresponse= uploadbytes(filename,redline_redaction_summary.content, s3uri)
                upload_responses.append(uploadresponse)
                #Upload to S3 ends
                if uploadresponse.status_code == 200:
                    summaryuploaderror= False    
                    summaryuploaderrormsg=""          
                else:
                    print("\n!!!ERROORR!!!",uploadresponse.text)
                    summaryuploaderror= True
                    summaryuploaderrormsg = uploadresponse.text
                pdfstitchjobactivity().recordjobstatus(message,4,"redactionsummaryuploaded",summaryuploaderror,summaryuploaderrormsg)
            #Invoke ZIP
        except (Exception) as error:
            print('error occured in redaction summary service: ', error)

   
    

