import logging
from utils import redisstreamdb, notification_stream_key
from rstreamio.message.schemas.notification import NotificationPublishSchema
from models import dedupeproducermessage
from datetime import datetime

import json

class redisstreamwriter:

    rdb = redisstreamdb
    notificationstream = rdb.Stream(notification_stream_key)

    def sendnotification(self, message, error=False):
        try:
            notification_msg = NotificationPublishSchema()
            notification_msg.serviceid = "dedupe"
            notification_msg.errorflag = self.__booltostr(error)
            notification_msg.ministryrequestid = message.ministryrequestid
            notification_msg.createdby = message.createdby
            notification_msg.createdat = datetime.now().strftime("%m/%d/%Y, %H:%M:%S.%f")
            notification_msg.batch = message.batch
            #Additional execution parameters : Begin
            
            #Additional execution parameters : End
            msgid = self.notificationstream.add(notification_msg.__dict__, id="*")
            logging.info("Notification message for msgid = %s ",  msgid)
        except RuntimeError as error:
            print("Exception while sending notification, func sendnotification(p4), Error : {0} ".format(error))
            logging.error("Unable to write to notification stream for batch %s | ministryrequestid=%i", message.batch, message.ministryrequestid)
            logging.error(error)

    def __booltostr(self, value):
        return "YES" if value == True else "NO"
