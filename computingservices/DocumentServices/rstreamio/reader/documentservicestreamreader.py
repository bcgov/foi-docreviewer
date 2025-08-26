import json
import typer
import random
import time
import logging
from enum import Enum
from utils import redisstreamdb
from utils.foidocumentserviceconfig import documentservice_stream_key
from services.redactionsummaryservice import redactionsummaryservice
from services.zippingservice import zippingservice


LAST_ID_KEY = "{consumer_id}:lastid"
BLOCK_TIME = 5000
STREAM_KEY = documentservice_stream_key

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
        messages = stream.read(last_id=last_id, block=BLOCK_TIME)
        if messages:
            for _message in messages:          
                # message_id is the random id created to identify the message
                # message is the actual data passed to the stream 
                message_id, message = _message 
                print(f"processing {message_id}::{message}")
                if message is not None:
                    message = json.dumps({str(key.decode("utf-8")): str(value.decode("utf-8")) for (key, value) in message.items()})
                    message_dict = json.loads(message)
                    category = message_dict.get("category")
                    summaryfiles = []
                    # TO DO: Get response package summary url & push it to the
                    # publication folder & zipper!
                    if category != "publicationpackage":
                        try:
                            summaryfiles = redactionsummaryservice().processmessage(message)
                        except(Exception) as error: 
                            logging.exception(error) 
                    zippingservice().sendtozipper(summaryfiles, message)   
                    # simulate processing
                time.sleep(random.randint(1, 3))
                last_id = message_id
                rdb.set(LAST_ID_KEY.format(consumer_id=consumer_id), last_id)
                print(f"finished processing {message_id}")
        else:
            logging.info(f"No new messages after ID: {last_id}")