import json
import typer
import random
import time
import logging
from enum import Enum
from utils import redisstreamdb
from utils.foidocumentserviceconfig import documentservice_stream_key, documentservice_block_time, documentservice_group_name, documentservice_consumer_name_prefix, documentservice_batch_size, documentservice_pod_name
from services.redactionsummaryservice import redactionsummaryservice
from services.zippingservice import zippingservice


app = typer.Typer()

class StartFrom(str, Enum):
    beginning = "0"
    latest = "$"

@app.command()
def start():
    rdb = redisstreamdb
    stream = rdb.Stream(documentservice_stream_key)

    while True:
        messages = stream.read_group(
            group=documentservice_group_name, 
            consumer=documentservice_consumer_name_prefix+"_"+documentservice_pod_name, 
            count=documentservice_batch_size, #5,  # Read a batch of messages
            block=documentservice_block_time
        )

        if messages:
            for message_id, message in messages:          
                # message_id is the random id created to identify the message
                # message is the actual data passed to the stream 
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
                stream.ack(group=documentservice_group_name, message_ids=[message_id])
                print(f"finished processing {message_id}")
        else:
            logging.info(f"No new messages in stream {documentservice_stream_key}. Waiting...")