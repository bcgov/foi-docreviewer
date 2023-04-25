import logging
from utils import notifcationstreamdb
from config import notification_stream_key, pdfstitch_failureattempt
from rstreamio.message.schemas.notification import NotificationPublishSchema


import json

class redisstreamwriter:
    max_retry_attempt = int(pdfstitch_failureattempt)
    rdb = notifcationstreamdb
    notificationstream = rdb.Stream(notification_stream_key)

    def sendnotification(self, message, error=False, totalskippedfilecount=0, totalskippedfiles=[], retry = 0):
        try:
            notification_msg = NotificationPublishSchema()
            notification_msg.serviceid = "pdfstitchforharms"
            notification_msg.errorflag = self.__booltostr(error)
            notification_msg.ministryrequestid = message.ministryrequestid
            notification_msg.createdby = message.createdby
            notification_msg.totalskippedfilecount = totalskippedfilecount
            notification_msg.totalskippedfiles = json.JSONEncoder().encode(totalskippedfiles)
            logging.info("Notification message = %s ",  notification_msg.__dict__)
            print("Notification message = %s ",  notification_msg.__dict__)
            msgid = self.notificationstream.add(notification_msg.__dict__, id="*")
            logging.info("Notification message for msgid = %s ",  msgid)
        except Exception as error:
            logging.error("Unable to write to notification stream for pdfstitch | ministryrequestid=%i", message.ministryrequestid)
            logging.error(error)
            if retry < self.max_retry_attempt:
                self.sendnotification(message, error, totalskippedfilecount, totalskippedfiles, retry + 1)
            else:
                print("Exceeded retry attempts for notification | ministryrequestid=%i", message.ministryrequestid)

    def __booltostr(self, value):
        return "YES" if value == True else "NO"
