import logging
from utils import redisstreamdb
from config import notification_stream_key
from rstreamio.message.schemas.notification import NotificationPublishSchema


import json

class redisstreamwriter:

    rdb = redisstreamdb
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
            msgid = self.notificationstream.add(notification_msg.__dict__, id="*")
            logging.info("Notification message for msgid = %s ",  msgid)
        except RuntimeError as error:
            logging.error("Unable to write to notification stream for pdfstitch | ministryrequestid=%i", message.ministryrequestid)
            logging.error(error)
        except Exception as error:
            print("error during the notification: ", error)

    def __booltostr(self, value):
        return "YES" if value == True else "NO"
