
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
            #Get Data ; Begin
            divisiondocuments = json.loads(message.summarydocuments)
            for entry in divisiondocuments:
                divisionid = entry['divisionid']
                documentids = entry['documentids']
                formattedsummary = redactionsummary().prepareredactionsummary(message, documentids)
                print(formattedsummary)
            #Get Data : End
            #Get Template
            #Document
            #Upload to S3
            #Invoke ZIP
            print(message)
            print(formattedsummary)
            print("\n\nmessage:",message)
            #Get Data
                       
            formattedsummary = redactionsummary().prepareredactionsummary(message)
            
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
                # Remove the filename and everything after it
                s3uri = s3uri[:last_slash_index + 1]
                #print("***Updated URI",s3uri)
                divisionname = messageattributes[0]['divisionname']
                #"redline" #get it from message
                requestnumber=formattedsummary["requestnumber"]
                filename = f"{requestnumber} - {category} - {divisionname} - summary"
                uploadobj= uploadbytes(filename,redline_redaction_summary.content, s3uri)
                upload_responses.append(uploadobj)
                #Upload to S3 ends
                if uploadobj["uploadresponse"].status_code == 200:
                    summaryuploaderror= False    
                    summaryuploaderrormsg=""          
                else:
                    print("\n!!!ERROORR!!!",uploadobj["uploadresponse"].text)
                    summaryuploaderror= True
                    summaryuploaderrormsg = uploadobj.uploadresponse.text
                pdfstitchjobactivity().recordjobstatus(message,4,"redactionsummaryuploaded",summaryuploaderror,summaryuploaderrormsg)
            #Invoke ZIP
            
            
            #print(message)
            
                
                filestozip= json.loads(message.filestozip)
                filestozip.append({"filename": uploadobj["filename"], "s3uripath":uploadobj["documentpath"]})
            #     msgattributesjson= json.loads(message.attributes)
            #     print("!!!!",msgattributesjson)
            #     print("!!!!type: ",type(msgattributesjson))

                
            #     filtered_list = [item for item in msgattributesjson if item.get('divisionid') == divisionid]
            #     filtered_list[0]['files']=filestozip
            #     print("filtered_list:",filtered_list)
            #     print("####TYPE of filtered_list : ####",type(filtered_list))
            #     print("msgattributesjson:",msgattributesjson)

            # # msgjson= json.loads(message)
            # # print("1updated_message_bytes:",msgjson)
            # print("$$$$$",type(message.filestozip))
            # filestozip_list = json.loads(message.filestozip)
            # print("####TYPE of filestozip : ####",type(filestozip_list))
            # filestozip_list=filestozip
            # print("$$$$$filestozip_list",filestozip_list)

            # # # Convert the updated dictionary back to bytes
            # # #updated_message_bytes = {key.encode('utf-8'): value.encode('utf-8') for key, value in message_dict.items()}
            # json_string = json.dumps(filestozip_list)
            # print("$$$$$json_string",json_string)
            # bytes_data = json_string.encode('utf-8')
            # message.filestozip =bytes_data
            # print("updated_message_bytes:",message)
            return filestozip
        except (Exception) as error:
            print('error occured in redaction summary service: ', error)

   
    

