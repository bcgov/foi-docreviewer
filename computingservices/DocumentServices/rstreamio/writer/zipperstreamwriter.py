import logging
from utils import redisstreamdb, zipper_stream_key
from rstreamio.message.schemas.zipper import ZipperPublishSchema
from models import dedupeproducermessage

import json

class zipperstreamwriter:

    rdb = redisstreamdb
    zipperstream = rdb.Stream(zipper_stream_key)

    def sendmessage(self, message, error=False):
        try:
            zipper_msg = ZipperPublishSchema()
            zipper_msg.serviceid = "documentservice"
            zipper_msg.errorflag = self.__booltostr(error)
            zipper_msg.ministryrequestid = message.ministryrequestid
            zipper_msg.createdby = message.createdby
            zipper_msg.batch = message.batch
            #Additional execution parameters : Begin
            
            #Additional execution parameters : End
            msgid = self.zipperstream.add(zipper_msg.__dict__, id="*")
            logging.info("Notification message for msgid = %s ",  msgid)
        except RuntimeError as error:
            print("Exception while sending notification, func sendnotification(p4), Error : {0} ".format(error))
            logging.error("Unable to write to notification stream for batch %s | ministryrequestid=%i", message.batch, message.ministryrequestid)
            logging.error(error)

    def __booltostr(self, value):
        return "YES" if value == True else "NO"
