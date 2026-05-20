import traceback
import json
import time
import logging
from services.dal.pdfstitchjobactivity import pdfstitchjobactivity
from .documentgenerationservice import documentgenerationservice
from .s3documentservice import uploadbytes
from services.dts.redactionsummary import redactionsummary
from services.dal.documentpageflag import documentpageflag
from rstreamio.message.schemas.redactionsummary import get_in_redactionsummary_msg, get_in_summary_object,get_in_summarypackage_object
from services.dal.documenttemplate import documenttemplate
from utils import getdbconnection, getfoidbconnection

class redactionsummaryservice():

    def processmessage(self,incomingmessage):
        start_total = time.time()
        summaryfilestozip = []
        message = get_in_redactionsummary_msg(incomingmessage)
        doc_conn = None
        foi_conn = None
        print('\n 1. get_in_redactionsummary_msg is : {0}'.format(message))
        try:
            category = message.category 
            #Condition to handle consults packaages (no summary files to be created)
            if category == "consultpackage": 
                return summaryfilestozip
            doc_conn = getdbconnection()
            foi_conn = getfoidbconnection()
            pdfstitchjobactivity().recordjobstatus(message,3,"redactionsummarystarted")                      
            summarymsg = message.summarydocuments
            #Condition for handling oipcredline category
            bcgovcode= message.bcgovcode
            requesttype = message.requesttype
            if bcgovcode == 'mcf' and requesttype == 'personal' and ("responsepackage" in category or category == 'openinfo'):
                documenttypename= 'CFD_responsepackage_redaction_summary'
            else:
                documenttypename= "responsepackage_redaction_summary" if ('responsepackage' in category or category == 'openinfo') else "redline_redaction_summary"
            print('\n 2. documenttypename', documenttypename)
            upload_responses=[]
            start_pageflags = time.time()
            pageflags = self.__get_pageflags(category, doc_conn=doc_conn)
            elapsed_pageflags = time.time() - start_pageflags
            logging.info(f"[PERF] redactionsummaryservice.__get_pageflags category={category} elapsed={elapsed_pageflags:.3f}s")

            start_progareas = time.time()
            programareas = documentpageflag().get_all_programareas(conn=foi_conn)
            elapsed_progareas = time.time() - start_progareas
            logging.info(f"[PERF] redactionsummaryservice.get_all_programareas elapsed={elapsed_progareas:.3f}s")

            messageattributes= json.loads(message.attributes)
            print("\n 3. messageattributes:",messageattributes)
            divisiondocuments = get_in_summary_object(summarymsg).pkgdocuments
            logging.info(f"[PERF] redactionsummaryservice divisiondocuments count={len(divisiondocuments)}")
            print("\n 4. divisiondocuments:",divisiondocuments)
            for entry in divisiondocuments:
                start_division = time.time()
                #print("\n entry:",entry)
                if 'documentids' in entry and len(entry['documentids']) > 0 :
                    print("\n 5. entry['divisionid']:",entry['divisionid'])
                    divisionid = entry['divisionid']
                    documentids = entry['documentids']
                    if message.documentsetid:
                        _documentids = documenttemplate.getrecordgroupsbyrequestid(message.ministryrequestid, documentids)
                        if _documentids:
                            documentids = _documentids
                    else:
                        documentids = documenttemplate.getcompatibledocumentids(documentids)
                    if not documentids:
                        continue
                    start_prepare = time.time()
                    formattedsummary = redactionsummary().prepareredactionsummary(message, documentids, pageflags, programareas, doc_conn=doc_conn)
                    elapsed_prepare = time.time() - start_prepare
                    logging.info(f"[PERF] redactionsummaryservice prepareredactionsummary divisionid={divisionid} docs={len(documentids)} elapsed={elapsed_prepare:.3f}s")

                    print("\n 6. formattedsummary", formattedsummary)
                    template_path='templates/'+documenttypename+'.docx'

                    start_generate = time.time()
                    redaction_summary= documentgenerationservice().generate_pdf(formattedsummary, documenttypename,template_path)
                    elapsed_generate = time.time() - start_generate
                    logging.info(f"[PERF] redactionsummaryservice generate_pdf divisionid={divisionid} template={documenttypename} elapsed={elapsed_generate:.3f}s")

                    divisioname = None
                    if len(messageattributes)>1:
                        filesobj=(next(item for item in messageattributes if item['divisionid'] == divisionid))['files'][0]
                        divisioname=(next(item for item in messageattributes if item['divisionid'] == divisionid))['divisionname'] if category not in ('responsepackage','oipcreviewredline', 'openinfo') else None
                        
                    else:
                        filesobj= messageattributes[0]['files'][0]
                        divisioname =  messageattributes[0]['divisionname'] if ('responsepackage' not in category and category != 'oipcreviewredline' and category != 'openinfo') else None  
                        
                    stitcheddocs3uri = filesobj['s3uripath']
                    stitcheddocfilename = filesobj['filename']
                    if category == 'oipcreviewredline':
                        s3uricategoryfolder = "oipcreview"
                    else:
                        s3uricategoryfolder = category
                    s3uri = stitcheddocs3uri.split(s3uricategoryfolder+"/")[0] + s3uricategoryfolder+"/"
                    summary_category= category
                    filename =self.__get_summaryfilename(message.requestnumber, summary_category, divisioname, stitcheddocfilename, message.phase)
                    print("\n redaction_summary.content length: {0}".format(len(redaction_summary.content)))

                    start_upload = time.time()
                    uploadobj= uploadbytes(filename,redaction_summary.content,s3uri)
                    elapsed_upload = time.time() - start_upload
                    logging.info(f"[PERF] redactionsummaryservice uploadbytes divisionid={divisionid} size={len(redaction_summary.content)} elapsed={elapsed_upload:.3f}s")

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

                if 'documentids' in entry and len(entry['documentids']) > 0:
                    elapsed_division = time.time() - start_division
                    logging.info(f"[PERF] redactionsummaryservice division loop complete divisionid={divisionid} elapsed={elapsed_division:.3f}s")

            elapsed_total = time.time() - start_total
            logging.info(f"[PERF] redactionsummaryservice.processmessage total processing finished elapsed={elapsed_total:.3f}s")
            return summaryfilestozip
        except (Exception) as error:
            traceback.print_exc()
            print('error occured in redaction summary service: ', error)
            pdfstitchjobactivity().recordjobstatus(message,4,"redactionsummaryfailed",str(error),"summary generation failed")
            return summaryfilestozip
        finally:
            if foi_conn is not None:
                foi_conn.close()
            if doc_conn is not None:
                doc_conn.close()
        
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
        elif category == 'openinfo':
                return "Redaction_Summary_" + requestnumber + ".pdf"
        else:
            _filename = requestnumber+" - "+category
            if divisionname not in (None, ''):
                _filename = _filename+" - "+divisionname    
        # print("---->",stitchedfilepath+_filename+" - summary.pdf")   
        return stitchedfilepath+_filename+" - summary.pdf"
  
    def __get_pageflags(self, category, doc_conn=None):
        if category in ("responsepackage", "openinfo"):            
            return documentpageflag().get_all_pageflags(['Consult', 'Not Responsive', 'Duplicate', 'Phase'], conn=doc_conn)
        return documentpageflag().get_all_pageflags(['Consult', 'Phase'], conn=doc_conn)
        

   
    
