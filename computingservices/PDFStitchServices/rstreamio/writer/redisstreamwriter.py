import logging
from utils import notifcationstreamdb, notifcationstreamdbwithparam
from config import notification_stream_key, pdfstitch_failureattempt, zip_enabled
from rstreamio.message.schemas.notification import NotificationPublishSchema


import json

class redisstreamwriter:
    max_retry_attempt = int(pdfstitch_failureattempt)
    if zip_enabled == "True":
        rdb = notifcationstreamdbwithparam
    else:
        rdb = notifcationstreamdb
    
    notificationstream = rdb.Stream(notification_stream_key)

    def sendnotification(self, message, error=False, totalskippedfilecount=0, totalskippedfiles=[]):
        try:
            notification_msg = NotificationPublishSchema()
            notification_msg.serviceid = "pdfstitchforharms"
            notification_msg.errorflag = self.__booltostr(error)
            notification_msg.ministryrequestid = message.ministryrequestid
            notification_msg.createdby = message.createdby
            notification_msg.totalskippedfilecount = totalskippedfilecount
            notification_msg.totalskippedfiles = json.JSONEncoder().encode(totalskippedfiles)
            logging.info("Notification message = %s ",  notification_msg.__dict__)
            print(f"Notification message =  {notification_msg.__dict__}")
            msgid = self.notificationstream.add(notification_msg.__dict__, id="*")
            logging.info("Notification message for msgid = %s ",  msgid)
        except Exception as error:
            logging.error(f"Unable to write to notification stream for pdfstitch | ministryrequestid= {message.ministryrequestid}")
            logging.error(error)
            # if retry < self.max_retry_attempt:
            #     self.sendnotification(message, error, totalskippedfilecount, totalskippedfiles, retry + 1)
            # else:
            #     print(f"Exceeded retry attempts for notification | ministryrequestid= {message.ministryrequestid}")

    def __booltostr(self, value):
        return "YES" if value == True else "NO"
