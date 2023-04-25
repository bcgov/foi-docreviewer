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
from utils import redisstreamdb
from config import division_pdf_stitch_stream_key, error_flag, zip_enabled
from rstreamio.message.schemas.divisionpdfstitch import get_in_divisionpdfmsg
from services.pdfstichservice import pdfstitchservice
from services.notificationservice import notificationservice
from rstreamio.writer.redisstreamwriter import redisstreamwriter


LAST_ID_KEY = "{consumer_id}:lastid"
BLOCK_TIME = 5000
STREAM_KEY = division_pdf_stitch_stream_key

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
        logging.info(f"Resume from ID: {last_id}")
    else:
        last_id = start_from.value
        logging.info(f"Starting from {start_from.name}")

    while True:
        logging.info("Reading stream...")
        messages = stream.read(last_id=last_id, block=BLOCK_TIME)
        if messages:
            for _messages in messages:          
                # message_id is the random id created to identify the message
                # message is the actual data passed to the stream 
                message_id, message = _messages 
                logging.info(f"processing {message_id}::{message}")
                handlemessage(message)                
                # simulate processing
                # time.sleep(random.randint(1, 3)) #TODO : todo: remove!
                last_id = message_id
                rdb.set(LAST_ID_KEY.format(consumer_id=consumer_id), last_id)
                logging.info(f"finished processing {message_id}")
        else:
            logging.info(f"No new messages after ID: {last_id}")

def handlemessage(message):

    if message is not None:
        _message = json.dumps({key.decode('utf-8'): value.decode('utf-8') for key, value in message.items()})
        _message = _message.replace("b'","'").replace("'",'')
        try:

            producermessage = get_in_divisionpdfmsg(_message)            
            pdfstitchservice().processmessage(producermessage)
            if zip_enabled == "True":
                # send notification for both success and error cases       
                notificationservice().sendnotification(producermessage)
        except(Exception) as error:
            logging.exception(error)