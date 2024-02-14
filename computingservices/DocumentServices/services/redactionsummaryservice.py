
import traceback
import json
from services.dal.pdfstitchjobactivity import pdfstitchjobactivity
from services.dts.redactionsummary import redactionsummary
from .documentgenerationservice import documentgenerationservice
from .s3documentservice import uploadbytes
from services.dts.redactionsummary import redactionsummary
from services.dal.documentpageflag import documentpageflag

class redactionsummaryservice():

    def processmessage(self,message):
        try:
            summaryfilestozip = []
            pdfstitchjobactivity().recordjobstatus(message,3,"redactionsummarystarted")
            divisiondocuments = message.summarydocuments
            #Condition for handling oipcredline category
            category = message.category if message.category == 'responsepackage' else "redline" 
            documenttypename= category+"_redaction_summary"
            print('documenttypename', documenttypename)
            upload_responses=[]
            pageflags = documentpageflag().get_all_pageflags()
            programareas = documentpageflag().get_all_programareas()
            summarymsg = message.summarydocuments
            divisiondocuments = summarymsg.pkgdocuments
            for entry in divisiondocuments:
                divisionid = entry.divisionid
                documentids = entry.documentids
                formattedsummary = redactionsummary().prepareredactionsummary(message, documentids, pageflags, programareas)
                print('formattedsummary', formattedsummary)
                template_path='templates/'+documenttypename+'.docx'
                redaction_summary= documentgenerationservice().generate_pdf(formattedsummary, documenttypename,template_path)
                messageattributes= message.attributes  
                if message.category == 'redline' :
                    filesobj=(next(item for item in messageattributes if item.divisionid == divisionid)).files[0]
                else:
                    filesobj= messageattributes[0].files[0]
                stitcheddocs3uri = filesobj.s3uripath
                stitcheddocfilename = filesobj.filename
                s3uri = stitcheddocs3uri.split(category+"/")[0] + category+"/"
                filename = stitcheddocfilename.replace(".pdf","- summary.pdf")
                print('s3uri:', s3uri)
                uploadobj= uploadbytes(filename,redaction_summary.content, s3uri)
                upload_responses.append(uploadobj)
                if uploadobj["uploadresponse"].status_code == 200:
                    summaryuploaderror= False    
                    summaryuploaderrormsg=""          
                else:
                    summaryuploaderror= True
                    summaryuploaderrormsg = uploadobj.uploadresponse.text
                pdfstitchjobactivity().recordjobstatus(message,4,"redactionsummaryuploaded",summaryuploaderror,summaryuploaderrormsg)
                summaryfilestozip.append({"filename": uploadobj["filename"], "s3uripath":uploadobj["documentpath"]})
            return summaryfilestozip
        except (Exception) as error:
            print('error occured in redaction summary service: ', error)
    
    

   
    

