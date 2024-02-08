
import traceback
import json
from services.dal.pdfstitchjobactivity import pdfstitchjobactivity
from services.dts.redactionsummary import redactionsummary
from .documentgenerationservice import documentgenerationservice
from .s3documentservice import uploadbytes
from services.dts.redactionsummary import redactionsummary
class redactionsummaryservice():

    def processmessage(self,message):
        try:
            filestozip=[]
            print("***BEFORE CALL TO pdfstitchjobactivity!!")
            pdfstitchjobactivity().recordjobstatus(message,3,"redactionsummarystarted")
            divisiondocuments = json.loads(message.summarydocuments)
            print("***divisiondocuments:",divisiondocuments)
            category = message.category
            documenttypename= category+"_redaction_summary"
            upload_responses=[]
            for entry in divisiondocuments:
                divisionid = entry['divisionid']
                documentids = entry['documentids']
                formattedsummary = redactionsummary().prepareredactionsummary(message, documentids)
                print("\n***Formattedsummary : ",divisionid)
                redline_redaction_summary= documentgenerationservice().generate_pdf(documenttypename,formattedsummary)
                print("\nFinished generate_pdf!!")
                messageattributes= json.loads(message.attributes)         
                s3uri = messageattributes[0]['files'][0]['s3uripath']
                # Find the last occurrence of '/'
                last_slash_index = s3uri.rfind('/')
                # Remove the filename and everything after it
                s3uri = s3uri[:last_slash_index + 1]
                s3uri = s3uri[:last_slash_index + 1]
                print("-->NEW S3",s3uri)
                divisionname= (next(item for item in messageattributes if item['divisionid'] == divisionid))['divisionname']
                print("-->divisionname",divisionname)
                requestnumber=formattedsummary["requestnumber"]
                filename = f"{divisionname}/{requestnumber} - {category} - {divisionname} - summary.pdf"
                uploadobj= uploadbytes(filename,redline_redaction_summary.content, s3uri)
                upload_responses.append(uploadobj)
                if uploadobj["uploadresponse"].status_code == 200:
                    summaryuploaderror= False    
                    summaryuploaderrormsg=""          
                else:
                    print("\n!!!ERROORR!!!",uploadobj["uploadresponse"].text)
                    summaryuploaderror= True
                    summaryuploaderrormsg = uploadobj.uploadresponse.text
                pdfstitchjobactivity().recordjobstatus(message,4,"redactionsummaryuploaded",summaryuploaderror,summaryuploaderrormsg)
                filestozip= json.loads(message.filestozip)
                filestozip.append({"filename": uploadobj["filename"], "s3uripath":uploadobj["documentpath"]})
            return filestozip
        except (Exception) as error:
            print('error occured in redaction summary service: ', error)
    
    def updatefilestozip(self,updatedfilestozip, _message):
        try:
            msgjson= json.loads(_message)
            filestozip_list = msgjson['filestozip']
            filestozip_list = json.loads(filestozip_list)
            #print("####TYPE of filestozip : ####",type(filestozip_list))
            filestozip_list=updatedfilestozip
            json_string = json.dumps(filestozip_list)
            bytes_data = json_string.encode('utf-8')
            msgjson['filestozip'] =bytes_data
            print("updated_message_bytes:",msgjson)
            return msgjson
        except (Exception) as error:
            print('error occured in redaction summary service: ', error)

   
    

