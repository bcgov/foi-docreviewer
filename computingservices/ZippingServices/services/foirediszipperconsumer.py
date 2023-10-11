"""
Start processing only latest records:
$ python consumer.py consumer1 --start-from $
Start processing all records in the stream from the beginning:
$ python consumer.py consumer1 --start-from 0
"""
import json
import typer
import random
import time
import logging
from enum import Enum
from utils import redisstreamdb, zipper_stream_key, jsonmessageparser
from .zipperservice import processmessage, sendnotification
from .notificationservice import notificationservice


LAST_ID_KEY = "{consumer_id}:lastid"
BLOCK_TIME = 5000
STREAM_KEY = zipper_stream_key

app = typer.Typer()


class StartFrom(str, Enum):
    beginning = "0"
    latest = "$"


@app.command()
def start(consumer_id: str, start_from: StartFrom = StartFrom.latest):
    try:
        rdb = redisstreamdb
        stream = rdb.Stream(STREAM_KEY)

        last_id = rdb.get(LAST_ID_KEY.format(consumer_id=consumer_id))
        if last_id:
            print(f"Resume from ID: {last_id}")
        else:
            last_id = start_from.value
            print(f"Starting from {start_from.name}")

        while True:
            # print("Reading stream...")
            messages = stream.read(last_id=last_id, block=BLOCK_TIME)
            if messages:
                for message_id, message in messages:
                    print(f"processing {message_id}::{message}")
                    if message is not None:
                        readyfornotification = False
                        producermessage = None
                        try:
                            _message = json.dumps(
                                {
                                    key.decode("utf-8"): value.decode("utf-8")
                                    for (key, value) in message.items()
                                }
                            )
                            producermessage = jsonmessageparser.getzipperproducermessage(
                                _message
                            )
                            print(producermessage)
                            processmessage(producermessage) 
                            readyfornotification = True
                            print(
                                "Processing is completed for Job ID {0} for category {1}".format(
                                    producermessage.jobid, producermessage.category
                                )
                            )
                            sendnotification(readyfornotification, producermessage)
                        except Exception as error:
                            print(
                                "Exception while processing redis message, func start(p1), Error : {0} ".format(
                                    str(error)
                                )
                            )
                        finally:
                            last_id = message_id
                            rdb.set(LAST_ID_KEY.format(consumer_id=consumer_id), last_id)
                            stream.delete(message_id)                                        
    except Exception as ex:
       print("Exception happened at the top level of zipper service: ", str(ex))