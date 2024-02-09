import json
import typer
import random
import time
import logging
from enum import Enum
from utils import redisstreamdb
from utils.foidocumentserviceconfig import pagecalculator_stream_key
from rstreamio.message.schemas.documentspagecount import get_in_documents_pagecount_msg
from services.pagecountservice.pagecountcalculationservice import pagecountcalculationservice

LAST_ID_KEY = "{consumer_id}:lastid"
BLOCK_TIME = 5000
STREAM_KEY = pagecalculator_stream_key

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
        print(f"PC Resume from ID: {last_id}")
    else:
        last_id = start_from.value
        print(f"PC Starting from {start_from.name}")

    while True:
        messages = stream.read(last_id=last_id, block=BLOCK_TIME)
        if messages:
            for _messages in messages:
                # message_id is the random id created to identify the message
                # message is the actual data passed to the stream 
                message_id, message = _messages 
                print(f"PC processing {message_id}::{message}")
                if message is not None:
                    _message = json.dumps({str(key): str(value) for (key, value) in message.items()})
                    _message = _message.replace("b'","'").replace("'",'')
                    try:
                        pagecountcalculationservice().processmessage(get_in_documents_pagecount_msg(_message))
                    except(Exception) as error: 
                        logging.exception(error)       
                    # simulate processing
                time.sleep(random.randint(1, 3)) #TODO : todo: remove!
                last_id = message_id
                rdb.set(LAST_ID_KEY.format(consumer_id=consumer_id), last_id)
                print(f"PC finished processing {message_id}")
        else:
            logging.info(f"PC No new messages after ID: {last_id}")