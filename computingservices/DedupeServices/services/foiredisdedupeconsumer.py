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
from utils import redisstreamdb,dedupe_stream_key,notification_stream_key
from . import jsonmessageparser
from .dedupeservice import processmessage
from .dedupedbservice import isbatchcompleted
from rstreamio.redisstreamwriter import redisstreamwriter

LAST_ID_KEY = "{consumer_id}:lastid"
BLOCK_TIME = 5000
STREAM_KEY = dedupe_stream_key

app = typer.Typer()


class StartFrom(str, Enum):
    beginning = "0"
    latest = "$"




@app.command()
def start(consumer_id: str, start_from: StartFrom = StartFrom.latest):
    rdb = redisstreamdb
    stream = rdb.Stream(STREAM_KEY)

    last_id = rdb.get(LAST_ID_KEY.format(consumer_id=consumer_id))
    if last_id:
        print(f"Resume from ID: {last_id}")
    else:
        last_id = start_from.value
        print(f"Starting from {start_from.name}")

    while True:
        #print("Reading stream...")
        messages = stream.read(last_id=last_id, block=BLOCK_TIME)
        if messages:
            for message_id, message in messages:
                print(f"processing {message_id}::{message}")
                if message is not None:                    
                    _message = json.dumps({str(key): str(value) for (key, value) in message.items()})
                    _message = _message.replace("b'","'").replace("'",'') 
                    try:
                        producermessage = jsonmessageparser.getdedupeproducermessage(_message)
                        processmessage(producermessage) 

                        # send message to notification stream if batch is complete
                        complete, err = isbatchcompleted(producermessage.batch)
                        if complete:
                            redisstreamwriter().sendnotification(producermessage, err)
                        else:
                            print("batch not yet complete, no message sent")
                    except(Exception) as error:
                        print("Exception while processing redis message, func start(p1), Error : {0} ".format(error))
                        logging.exception(error)
                                            
                # simulate processing
                #time.sleep(random.randint(1, 3)) #TODO : todo: remove!
                last_id = message_id
                rdb.set(LAST_ID_KEY.format(consumer_id=consumer_id), last_id)
                print(f"finished processing {message_id}")
        #else:
            #print(f"No new messages after ID: {last_id}")
