
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
            #Get Template           
            receipt_template={
                "extension":"docx",
                "cdogs_hash_code":"58G94G"
            }
            formattedsummary = redactionsummary().prepareredactionsummary(message)
            print(formattedsummary)
            # formattedsummary={'requestnumber': 'EDU-20240125-1',
            #                    'data': [{'flagname': 'PARTIAL DISCLOSURE', 'pagecount': 4, 
            #                     'sections': [{'range': 1, 'section': 'Partial Disclosure under s. 15'}, {'range': '5-7','section': 'Partial Disclosure under s. 15,s. 16,s. 13,s. 17,s. 12'}]}, {'flagname': 'WITHHELD IN FULL', 'pagecount': 1, 
            #                     'sections': [{'range': 3, 'section': 'Withheld in Full under s. 15,s. 13,s. 12'}]}, {'flagname': 'DUPLICATE', 'pagecount': 2, 
            #                     'sections': [{'range': 2, 'section': 'Duplicate'}, {'range': 4, 'section': 'Duplicate'}]}]}
            print("\nBefore calling generate_pdf:", json.dumps(message.attributes) )
            receipt_template_path= r'templates/redline_redaction_summary.docx'
            redline_redaction_summary= documentgenerationservice().generate_pdf(receipt_template,formattedsummary,receipt_template_path)
            print("Finished generate_pdf!!")
            #Method for calling the pdf generation method ends
            #Document
            #Upload to S3 starts
            messagejson=json.loads(message)
            messageattributes= messagejson.attributes
            s3uri = messageattributes[0]['files'][0]['s3uripath']
            # Find the last occurrence of '/'
            last_slash_index = s3uri.rfind('/')
            # Remove the filename and everything after it
            s3uri = s3uri[:last_slash_index + 1]
            divisionname = messageattributes[0]['divisionname']
            category = messagejson.category #"redline" #get it from message
            requestnumber=formattedsummary["requestnumber"]
            filename = f"{requestnumber} - {category} - {divisionname} - summary"
            print("\nBefore calling uploadbytes", s3uri )
            uploadbytes(filename,redline_redaction_summary.content, s3uri)
            #Upload to S3 ends
            #Invoke ZIP
        except (Exception) as error:
            print('error occured in redaction summary service: ', error)
    
    

