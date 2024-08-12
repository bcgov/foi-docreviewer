
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
        #Condition to handle consults packaages (no summary files to be created)
        if message.category == "consultpackage":
            return summaryfilestozip
        try:
            pdfstitchjobactivity().recordjobstatus(message,3,"redactionsummarystarted")                      
            summarymsg = message.summarydocuments
            #Condition for handling oipcredline category
            bcgovcode= message.bcgovcode
            category = message.category 
            if bcgovcode == 'mcf' and category == 'responsepackage':
                documenttypename= 'CFD_responsepackage_redaction_summary'
            else:
                documenttypename= category+"_redaction_summary" if category == 'responsepackage' else "redline_redaction_summary"
            #print('documenttypename', documenttypename)
            upload_responses=[]
            pageflags = self.__get_pageflags(category)
            programareas = documentpageflag().get_all_programareas()
            messageattributes= json.loads(message.attributes)
            #print("\nmessageattributes:",messageattributes)
            divisiondocuments = get_in_summary_object(summarymsg).pkgdocuments
            #print("\n divisiondocuments:",divisiondocuments)
            for entry in divisiondocuments:
                #print("\n entry:",entry)
                if 'documentids' in entry and len(entry['documentids']) > 0 :
                    # print("\n entry['divisionid']:",entry['divisionid'])
                    divisionid = entry['divisionid']
                    documentids = entry['documentids']
                    formattedsummary = redactionsummary().prepareredactionsummary(message, documentids, pageflags, programareas)
                    #print("formattedsummary", formattedsummary)
                    template_path='templates/'+documenttypename+'.docx'
                    redaction_summary= documentgenerationservice().generate_pdf(formattedsummary, documenttypename,template_path)
                    divisioname = None
                    if len(messageattributes)>1:
                        filesobj=(next(item for item in messageattributes if item['divisionid'] == divisionid))['files'][0]
                        divisioname=(next(item for item in messageattributes if item['divisionid'] == divisionid))['divisionname'] if category not in ('responsepackage','oipcreviewredline') else None
                        
                    else:
                        filesobj= messageattributes[0]['files'][0]
                        divisioname =  messageattributes[0]['divisionname'] if category not in ('responsepackage','oipcreviewredline') else None  
                        
                    stitcheddocs3uri = filesobj['s3uripath']
                    stitcheddocfilename = filesobj['filename'] 
                    if category == 'oipcreviewredline':
                        s3uricategoryfolder = "oipcreview"
                    else:
                        s3uricategoryfolder = category
                    s3uri = stitcheddocs3uri.split(s3uricategoryfolder+"/")[0] + s3uricategoryfolder+"/"
                    filename =self.__get_summaryfilename(message.requestnumber, category, divisioname, stitcheddocfilename) 
                    # print("\n filename:",filename)
                    uploadobj= uploadbytes(filename,redaction_summary.content,s3uri)
                    upload_responses.append(uploadobj)
                    if uploadobj["uploadresponse"].status_code == 200:
                        summaryuploaderror= False    
                        summaryuploaderrormsg=""          
                    else:
                        summaryuploaderror= True
                        summaryuploaderrormsg = uploadobj.uploadresponse.text
                    pdfstitchjobactivity().recordjobstatus(message,4,"redactionsummaryuploaded",summaryuploaderror,summaryuploaderrormsg)
                    # print("\ns3uripath:",uploadobj["documentpath"])
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
        # print("---->",stitchedfilepath+_filename+" - summary.pdf")   
        return stitchedfilepath+_filename+" - summary.pdf"
  
    def __get_pageflags(self, category):
        if category == "responsepackage":            
            return documentpageflag().get_all_pageflags(['Consult', 'Not Responsive', 'Duplicate'])
        return documentpageflag().get_all_pageflags(['Consult'])
        

   
    

