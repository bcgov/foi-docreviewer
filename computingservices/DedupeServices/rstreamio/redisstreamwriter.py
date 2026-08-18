import logging
from utils import redisstreamdb, notification_stream_key
from rstreamio.message.schemas.notification import NotificationPublishSchema
from datetime import datetime
from utils.loggingutils import log_event


logger = logging.getLogger(__name__)

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
            log_event(
                logger,
                logging.INFO,
                "notification_published",
                context=message,
                stream_id=msgid,
            )
        except RuntimeError as error:
            log_event(
                logger,
                logging.ERROR,
                "notification_publish_failed",
                context=message,
                exc_info=True,
            )

    def __booltostr(self, value):
        return "YES" if value == True else "NO"
