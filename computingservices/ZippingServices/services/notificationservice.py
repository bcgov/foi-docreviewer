from .zipperdboperations import ispdfstichjobcompleted
from utils.foizipperconfig import notification_stream_key
from utils.foiredisstreamdb import notificationredisstreamdb
from models.harrmsnotificationmessage import harmsnotificationmessage

import logging,json

class notificationservice:

    def sendharmsnotification(self,producermessage):

        complete, err, total_skippedfilecount, skippedfiles = self.__ispdfstitchjobcompleted(producermessage.jobid, producermessage.category.lower())

        if complete or err:
            self.__publishtostream(producermessage, err, total_skippedfilecount, skippedfiles)
        else:
            logging.info("pdfstitch not yet complete, no message sent")



    def __publishtostream(self, message, error=False, totalskippedfilecount=0, totalskippedfiles=[]):
        try:
            notification_msg = harmsnotificationmessage(ministryrequestid=message.ministryrequestid,serviceid="pdfstitchforharms",
                                totalskippedfilecount=totalskippedfilecount ,totalskippedfiles=json.JSONEncoder().encode(totalskippedfiles),createdby=message.createdby,errorflag=self.__booltostr(error))                                                    
           
            logging.info("Notification message = %s ",  notification_msg.__dict__)
            print(f"Notification message =  {notification_msg.__dict__}")
            notificationstream = notificationredisstreamdb.Stream(notification_stream_key)

            msgid = notificationstream.add(notification_msg.__dict__, id="*")
            logging.info("Notification message for msgid = %s ",  msgid)
        except Exception as error:
            logging.error(f"Unable to write to notification stream for pdfstitch | ministryrequestid= {message.ministryrequestid}")
            logging.error(error)

    def __booltostr(self, value):
        return "YES" if value == True else "NO"
    
    def __getskippedfiledetails(self, data):
        total_skippedfilecount = 0
        total_skippedfiles = []

        print('data stitchedoutput is {0}'.format(data))
        data = json.loads(data)
        for output in data['stitchedoutput']:
            skippedfilecount = output['skippedfilecount']
            skippedfiles = output['skippedfiles']
            total_skippedfilecount += skippedfilecount
            total_skippedfiles.extend(skippedfiles)
        
        total_skippedfiles = list(set(total_skippedfiles))
        return total_skippedfilecount, total_skippedfiles

    def __ispdfstitchjobcompleted(self, jobid, category):
        total_skippedfilecount = 0
        skippedfiles = None
        complete, err, attributes = ispdfstichjobcompleted(jobid, category)
        if attributes:
            total_skippedfilecount, skippedfiles = self.__getskippedfiledetails(attributes)
        return complete, err, total_skippedfilecount, skippedfiles
     

