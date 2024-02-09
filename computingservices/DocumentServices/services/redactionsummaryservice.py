
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
            pdfstitchjobactivity().recordjobstatus(message,3,"redactionsummarystarted")
            divisiondocuments = json.loads(message.summarydocuments)
            category = message.category
            documenttypename= category+"_redaction_summary"
            upload_responses=[]
            for entry in divisiondocuments:
                divisionid = entry['divisionid']
                documentids = entry['documentids']
                formattedsummary = redactionsummary().prepareredactionsummary(message, documentids)
                template_path='templates/'+documenttypename+'.docx'
                redaction_summary= documentgenerationservice().generate_pdf(documenttypename,formattedsummary,template_path)
                messageattributes= json.loads(message.attributes)         
                s3uri = (next(item for item in messageattributes if item['divisionid'] == divisionid))['files'][0]['s3uripath']
                last_slash_index = s3uri.rfind('/')
                s3uri = s3uri[:last_slash_index]
                last_slash_index = s3uri.rfind('/')
                s3uri = s3uri[:last_slash_index + 1]
                divisionname= (next(item for item in messageattributes if item['divisionid'] == divisionid))['divisionname']
                requestnumber=formattedsummary["requestnumber"]
                filename = f"{divisionname}/{requestnumber} - {category} - {divisionname} - summary.pdf"
                uploadobj= uploadbytes(filename,redaction_summary.content, s3uri)
                upload_responses.append(uploadobj)
                if uploadobj["uploadresponse"].status_code == 200:
                    summaryuploaderror= False    
                    summaryuploaderrormsg=""          
                else:
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
            filestozip_list=updatedfilestozip
            json_string = json.dumps(filestozip_list)
            bytes_data = json_string.encode('utf-8')
            msgjson['filestozip'] =bytes_data
            return msgjson
        except (Exception) as error:
            print('error occured in redaction summary service: ', error)

   
    

