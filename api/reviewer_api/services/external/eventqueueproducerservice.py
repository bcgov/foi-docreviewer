import os
from walrus import Database
from reviewer_api.models.default_method_result import DefaultMethodResult
import logging
from os import getenv


class eventqueueproducerservice:
    """This class is reserved for integration with event queue (currently redis streams)."""

    host = os.getenv("ZIPPER_REDIS_HOST")
    port = os.getenv("ZIPPER_REDIS_PORT")
    password = os.getenv("ZIPPER_REDIS_PASSWORD")

    db = Database(host=host, port=port, db=0, password=password)

    def add(self, streamkey, payload):
        try:
            stream = self.db.Stream(streamkey)
            msgid = stream.add(payload, id="*")
            return DefaultMethodResult(True, "Added to stream", msgid.decode("utf-8"))
        except Exception as err:
            logging.error("Error in contacting Redis Stream")
            logging.error(err)
            return DefaultMethodResult(False, err, -1)
