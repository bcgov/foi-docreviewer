
import traceback
import json
from services.dal.pdfstitchjobactivity import pdfstitchjobactivity
from services.dts.redactionsummary import redactionsummary
from .documentgenerationservice import documentgenerationservice
from .s3documentservice import uploadbytes
from services.dts.redactionsummary import redactionsummary
from services.dal.documentpageflag import documentpageflag
from rstreamio.message.schemas.redactionsummary import get_in_redactionsummary_msg, get_in_summary_object,get_in_summarypackage_object
class redactionsummaryservice():

    def processmessage(self,incomingmessage):
        summaryfilestozip = []
        message = get_in_redactionsummary_msg(incomingmessage)
        try:
            pdfstitchjobactivity().recordjobstatus(message,3,"redactionsummarystarted")                      
            summarymsg = message.summarydocuments
            #Condition for handling oipcredline category
            #bcgovcode= message.bcgovcode
            category = message.category  
            documenttypename= category+"_redaction_summary" if category == 'responsepackage' or category == 'CFD_responsepackage' else "redline_redaction_summary"
            #print('documenttypename', documenttypename)
            upload_responses=[]
            pageflags = self.__get_pageflags(category)
            programareas = documentpageflag().get_all_programareas()
            messageattributes= json.loads(message.attributes)
            print("\nmessageattributes:",messageattributes)
            divisiondocuments = get_in_summary_object(summarymsg).pkgdocuments
            for entry in divisiondocuments:
                if 'documentids' in entry and len(entry['documentids']) > 0:
                    divisionid = entry['divisionid']
                    documentids = entry['documentids']
                    formattedsummary = redactionsummary().prepareredactionsummary(message, documentids, pageflags, programareas, messageattributes)
                    print("formattedsummary", formattedsummary)
                    template_path='templates/'+documenttypename+'.docx'
                    redaction_summary= documentgenerationservice().generate_pdf(formattedsummary, documenttypename,template_path)
                    #messageattributes= json.loads(message.attributes)
                    divisioname = None
                    if len(messageattributes)>1:
                        filesobj=(next(item for item in messageattributes if item['divisionid'] == divisionid))['files'][0]
                        divisioname=(next(item for item in messageattributes if item['divisionid'] == divisionid))['divisionname'] if category not in ('responsepackage','oipcreviewredline', 'CFD_responsepackage') else None
                        
                    else:
                        filesobj= messageattributes[0]['files'][0]
                        divisioname =  messageattributes[0]['divisionname'] if category not in ('responsepackage','oipcreviewredline', 'CFD_responsepackage') else None  
                        
                    stitcheddocs3uri = filesobj['s3uripath']
                    stitcheddocfilename = filesobj['filename']                    
                    s3uricategoryfolder= "oipcreview" if category == 'oipcreviewredline' else category
                    s3uri = stitcheddocs3uri.split(s3uricategoryfolder+"/")[0] + s3uricategoryfolder+"/"
                    filename =self.__get_summaryfilename(message.requestnumber, category, divisioname, stitcheddocfilename) 
                    uploadobj= uploadbytes(filename,redaction_summary.content,s3uri)
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
        
    def __get_summaryfilename(self, requestnumber, category, divisionname, stitcheddocfilename):
        stitchedfilepath = stitcheddocfilename[:stitcheddocfilename.rfind( '/')+1]
        if category == 'responsepackage':
            _filename = requestnumber
        elif category == 'oipcreviewredline':
            _filename = requestnumber+ ' - Redline'
        else:
            _filename = requestnumber+" - "+category
            if divisionname not in (None, ''):
                _filename = _filename+" - "+divisionname    
        print("---->",stitchedfilepath+_filename+" - summary.pdf")   
        return stitchedfilepath+_filename+" - summary.pdf"
  
    def __get_pageflags(self, category):
        if category == "responsepackage":            
            return documentpageflag().get_all_pageflags(['Consult', 'Not Responsive', 'Duplicate'])
        return documentpageflag().get_all_pageflags(['Consult'])
        

   
    

