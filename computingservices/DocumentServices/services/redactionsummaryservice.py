
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
        print('\n 1. get_in_redactionsummary_msg is : {0}'.format(message))
        try:
            category = message.category 
            #Condition to handle consults packaages (no summary files to be created)
            if category == "consultpackage": 
                return summaryfilestozip
            pdfstitchjobactivity().recordjobstatus(message,3,"redactionsummarystarted")                      
            summarymsg = message.summarydocuments
            #Condition for handling oipcredline category
            bcgovcode= message.bcgovcode
            requesttype = message.requesttype
            if bcgovcode == 'mcf' and requesttype == 'personal' and 'responsepackage' in category:
                documenttypename= 'CFD_responsepackage_redaction_summary'
            else:
                documenttypename= "responsepackage_redaction_summary" if 'responsepackage' in category else "redline_redaction_summary"
            print('\n 2. documenttypename', documenttypename)
            upload_responses=[]
            pageflags = self.__get_pageflags(category)
            programareas = documentpageflag().get_all_programareas()
            messageattributes= json.loads(message.attributes)
            print("\n 3. messageattributes:",messageattributes)
            divisiondocuments = get_in_summary_object(summarymsg).pkgdocuments
            print("\n 4. divisiondocuments:",divisiondocuments)
            for entry in divisiondocuments:
                #print("\n entry:",entry)
                if 'documentids' in entry and len(entry['documentids']) > 0 :
                    print("\n 5. entry['divisionid']:",entry['divisionid'])
                    divisionid = entry['divisionid']
                    documentids = entry['documentids']
                    formattedsummary = redactionsummary().prepareredactionsummary(message, documentids, pageflags, programareas)
                    print("\n 6. formattedsummary", formattedsummary)
                    template_path='templates/'+documenttypename+'.docx'
                    redaction_summary= documentgenerationservice().generate_pdf(formattedsummary, documenttypename,template_path)
                    print("redaction_summary:",redaction_summary)
                    divisioname = None
                    if len(messageattributes)>1:
                        filesobj=(next(item for item in messageattributes if item['divisionid'] == divisionid))['files'][0]
                        divisioname=(next(item for item in messageattributes if item['divisionid'] == divisionid))['divisionname'] if category not in ('responsepackage','oipcreviewredline') else None
                        
                    else:
                        filesobj= messageattributes[0]['files'][0]
                        divisioname =  messageattributes[0]['divisionname'] if ('responsepackage' not in category and category != 'oipcreviewredline') else None  
                        
                    stitcheddocs3uri = filesobj['s3uripath']
                    stitcheddocfilename = filesobj['filename']
                    print("stitcheddocs3uri: ",stitcheddocs3uri)
                    if category == 'oipcreviewredline':
                        s3uricategoryfolder = "oipcreview"
                    else:
                        s3uricategoryfolder = category
                    print("s3uricategoryfolder:",s3uricategoryfolder)
                    s3uri = stitcheddocs3uri.split(s3uricategoryfolder+"/")[0] + s3uricategoryfolder+"/"
                    # phased redline filename adjustment
                    summary_category= category
                    if category in ("redlinephase" , "responsepackagephase") and (message.phase is not None and message.phase != ""):
                        summary_category= f'Redline - Phase {message.phase}' if category == "redlinephase" else f'ResponsePackage - Phase {message.phase}'
                    filename =self.__get_summaryfilename(message.requestnumber, summary_category, divisioname, stitcheddocfilename, message.phase)
                    print("\n redaction_summary.content length: {0}".format(len(redaction_summary.content)))
                    print("filename: ",filename)
                    print("s3uri: ",s3uri)
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
            traceback.print_exc()
            print('error occured in redaction summary service: ', error)
            pdfstitchjobactivity().recordjobstatus(message,4,"redactionsummaryfailed",str(error),"summary generation failed")
            return summaryfilestozip
        
    def __get_summaryfilename(self, requestnumber, category, divisionname, stitcheddocfilename, phase):
        stitchedfilepath = stitcheddocfilename[:stitcheddocfilename.rfind( '/')+1]
        if 'responsepackage' in category:
            if 'phase' in category and phase not in ("", None):
                _filename = requestnumber+ f' - Phase {phase}'
            else:
                _filename = requestnumber
        elif 'redline' in category and phase not in ("", None):
            _filename = requestnumber+ f' - Redline - Phase {phase}'
        elif category == 'oipcreviewredline':
            _filename = requestnumber+ ' - Redline'
        else:
            _filename = requestnumber+" - "+category
            if divisionname not in (None, ''):
                _filename = _filename+" - "+divisionname    
        # print("---->",stitchedfilepath+_filename+" - summary.pdf")   
        return stitchedfilepath+_filename+" - summary.pdf"
  
    def __get_pageflags(self, category):
        if 'responsepackage' in category:            
            return documentpageflag().get_all_pageflags(['Consult', 'Not Responsive', 'Duplicate', 'Phase'])
        return documentpageflag().get_all_pageflags(['Consult', 'Phase'])
        

   
    

