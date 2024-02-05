
import traceback
import json
from services.dal.pdfstitchjobactivity import pdfstitchjobactivity
from .documentgenerationservice import documentgenerationservice
from .s3documentservice import uploadbytes
from services.dts.redactionsummary import redactionsummary
class redactionsummaryservice():

    def processmessage(self,message):
        try:
            print("\n\nBEFORE CALL TO pdfstitchjobactivity!!")
            pdfstitchjobactivity().recordjobstatus(message,3,"redactionsummarystarted")
            print("\n\nmessage:",message)
            #Get Data
                       
            formattedsummary = redactionsummary().prepareredactionsummary(message)
            
            #TODO : For each division generate the pdf & upload to respective folders!!
            print("\n**Formattedsummary:",formattedsummary)
            print("\nBefore calling generate_pdf:", json.dumps(message.attributes))
            messagejson=json.loads(message)
            messageattributes= messagejson.attributes
            category = messagejson.category
            documenttypename= category+"_redaction_summary"
            #receipt_template_path= r'templates/redline_redaction_summary.docx'
            #Get Template
            redline_redaction_summary= documentgenerationservice().generate_pdf(documenttypename,formattedsummary,receipt_template_path)
            print("Finished generate_pdf!!")
            #Method for calling the pdf generation method ends
            #Document
            #Upload to S3 starts         
            s3uri = messageattributes[0]['files'][0]['s3uripath']
            # Find the last occurrence of '/'
            last_slash_index = s3uri.rfind('/')
            # Remove the filename and everything after it
            s3uri = s3uri[:last_slash_index + 1]
            divisionname = messageattributes[0]['divisionname']
             #"redline" #get it from message
            requestnumber=formattedsummary["requestnumber"]
            filename = f"{requestnumber} - {category} - {divisionname} - summary"
            print("\nBefore calling uploadbytes", s3uri )
            uploadresponse= uploadbytes(filename,redline_redaction_summary.content, s3uri)
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
    
    

