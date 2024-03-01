
import traceback
import json
from services.dal.pdfstitchjobactivity import pdfstitchjobactivity
from services.dts.redactionsummary import redactionsummary
from .documentgenerationservice import documentgenerationservice
from .s3documentservice import uploadbytes
from services.dts.redactionsummary import redactionsummary
from services.dal.documentpageflag import documentpageflag
from rstreamio.message.schemas.redactionsummary import get_in_redactionsummary_msg
class redactionsummaryservice():

    def processmessage(self,incomingmessage):
        summaryfilestozip = []
        message = get_in_redactionsummary_msg(incomingmessage)
        try:
            pdfstitchjobactivity().recordjobstatus(message,3,"redactionsummarystarted")                      
            summarymsg = message.summarydocuments
            #Condition for handling oipcredline category
            category = message.category  
            documenttypename= category+"_redaction_summary" if category == 'responsepackage' else "redline_redaction_summary"
            #print('documenttypename', documenttypename)
            upload_responses=[]
            pageflags = documentpageflag().get_all_pageflags()
            programareas = documentpageflag().get_all_programareas()
            divisiondocuments = summarymsg.pkgdocuments
            for entry in divisiondocuments:
                divisionid = entry.divisionid
                documentids = entry.documentids
                formattedsummary = redactionsummary().prepareredactionsummary(message, documentids, pageflags, programareas)
                print('formattedsummary', formattedsummary)
                template_path='templates/'+documenttypename+'.docx'
                redaction_summary= documentgenerationservice().generate_pdf(formattedsummary, documenttypename,template_path)
                messageattributes= message.attributes  
                print("attributes length:",len(messageattributes))
                if len(messageattributes)>1:
                    filesobj=(next(item for item in messageattributes if item.divisionid == divisionid)).files[0]
                else:
                    filesobj= messageattributes[0].files[0]
                stitcheddocs3uri = filesobj.s3uripath
                stitcheddocfilename = filesobj.filename
                s3uricategoryfolder= "oipcreview" if category == 'oipcreviewredline' else category
                s3uri = stitcheddocs3uri.split(s3uricategoryfolder+"/")[0] + s3uricategoryfolder+"/"
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
            pdfstitchjobactivity().recordjobstatus(message,4,"redactionsummaryfailed",str(error),"summary generation failed")
            return summaryfilestozip

   
    

