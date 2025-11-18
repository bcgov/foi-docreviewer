import json
import typer
import random
import time
import logging
from enum import Enum
from utils.foiredisstreamdbnew import redisstreamdbnew
from utils.foidocumentserviceconfig import documentservice_stream_key, documentservice_block_time, documentservice_group_name, documentservice_consumer_name_prefix, documentservice_batch_size, documentservice_pod_name, documentservice_timeout
from services.redactionsummaryservice import redactionsummaryservice
from services.zippingservice import zippingservice

CONSUMER_NAME = documentservice_consumer_name_prefix + "_" + documentservice_pod_name

app = typer.Typer()

# class StartFrom(str, Enum):
#     beginning = "0"
#     latest = "$"

@app.command()
def start():
    rdb = redisstreamdbnew
    stream = rdb.Stream(documentservice_stream_key)

    try:
        # create consumer group, starting from the beginning '0'
        stream.create_group(documentservice_group_name, start_id='0', ignore_exists=True)
        logging.info(f"Consumer group {documentservice_group_name} created or verified.")
    except Exception as e:
        logging.warning(f"Failed to create consumer group {documentservice_group_name}: {e}")

    claimed_messages = stream.autoclaim(
        documentservice_group_name, 
        CONSUMER_NAME,
        documentservice_timeout,
        '0-0', # Start from the beginning of the PEL
        documentservice_batch_size
    )

    if claimed_messages:
        logging.warning(f"Claimed {len(claimed_messages)} stale messages from PEL.")
        # Process the claimed messages immediately
        for message_id, message in claimed_messages:
            print(f"**PEL CLAIMED** processing {message_id}::{message}")
            processmessage(message_id, message, stream)
            print(f"**PEL CLAIMED** finished processing and ACKed {message_id}")

    while True:
        messages = stream.read_group(
            documentservice_group_name,
            CONSUMER_NAME,
            documentservice_batch_size, #5,  # Read a batch of messages
            documentservice_block_time,
            '>'    # Read new messages only
        )

        if messages:
            for message_id, message in messages:
                # message_id is the random id created to identify the message
                # message is the actual data passed to the stream 
                processmessage(message_id, message, stream)
                # time.sleep(random.randint(1, 3))
        else:
            logging.info(f"No new messages in stream {documentservice_stream_key}. Waiting...")

def processmessage(message_id, message, stream):
    try:
        str_id = message_id.decode()
        print(f"processing {str_id}::{message}")
        if message is not None:
            # Decode keys and values from bytes to strings
            message_dict = {
                k.decode("utf-8"): v.decode("utf-8") for (k, v) in message.items()
            }

            # Re-serialize to JSON string for consumption by services
            message_json_string = json.dumps(message_dict)
            category = message_dict.get("category")
            summaryfiles = []
            # TO DO: Get response package summary url & push it to the
            # publication folder & zipper!
            if category != "publicationpackage":
                try:
                    summaryfiles = redactionsummaryservice().processmessage(message_json_string)
                except(Exception) as error: 
                    logging.exception(error) 
            zippingservice().sendtozipper(summaryfiles, message_json_string)   
            # simulate processing
        stream.ack(documentservice_group_name, [message_id])
        print(f"finished processing {str_id}")
    except Exception as e:
        logging.exception(f"Error processing message {message_id.decode()}: {e}")