import logging
from utils import redisstreamdb, zipper_stream_key


class zipperstreamwriter:

    rdb = redisstreamdb
    zipperstream = rdb.Stream(zipper_stream_key)

    def sendmessage(self, message):
        try:
            msgid = self.zipperstream.add(message, id="*")
            logging.info("zipper message for msgid = %s ",  msgid)
        except RuntimeError as error:
            print("Exception while sending message for zipping , Error : {0} ".format(error))
            logging.error("Unable to write to message stream for zipper %s | ministryrequestid=%i", message.ministryrequestid, message.ministryrequestid)
            logging.error(error)

    