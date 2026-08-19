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
from .dedupeservice import initialize_compressionproducer, processmessage
from .dedupedbservice import isbatchcompleted
from rstreamio.redisstreamwriter import redisstreamwriter
from utils.loggingutils import log_context, log_event

LAST_ID_KEY = "{consumer_id}:lastid"
BLOCK_TIME = 5000
STREAM_KEY = dedupe_stream_key

app = typer.Typer()
logger = logging.getLogger(__name__)


class StartFrom(str, Enum):
    beginning = "0"
    latest = "$"




@app.command()
def start(consumer_id: str, start_from: StartFrom = StartFrom.latest):
    initialize_compressionproducer()
    rdb = redisstreamdb
    stream = rdb.Stream(STREAM_KEY)
    consumer_context = log_context(consumer_id=consumer_id)
    last_id = rdb.get(LAST_ID_KEY.format(consumer_id=consumer_id))
    if last_id:
        log_event(logger, logging.INFO, "consumer_resumed", context=consumer_context, stream_id=last_id)
    else:
        last_id = start_from.value
        log_event(logger, logging.INFO, "consumer_started", context=consumer_context)

    while True:
        #print("Reading stream...")
        messages = stream.read(last_id=last_id, block=BLOCK_TIME)
        if messages:
            for message_id, message in messages:
                if message is not None:
                    started_at = time.monotonic()
                    message_context = log_context(consumer_id=consumer_id, stream_id=message_id)
                    log_event(logger, logging.INFO, "message_received", context=message_context)
                    stage = "message_parse"
                    try:
                        _message = json.dumps({key.decode('utf-8'): value.decode('utf-8') for (key, value) in message.items()})
                        producermessage = jsonmessageparser.getdedupeproducermessage(_message)
                        message_context = log_context(producermessage, **message_context)
                        log_event(logger, logging.INFO, "message_parsed", context=message_context)
                        stage = "dedupe_processing"
                        processmessage(producermessage, log_context_data=message_context)
                        # send message to notification stream if batch is complete
                        stage = "batch_check"
                        complete, err = isbatchcompleted(producermessage.batch)
                        log_event(logger, logging.INFO, "batch_checked", context=message_context)
                        if complete:
                            stage = "notification_publish"
                            redisstreamwriter().sendnotification(producermessage, err)
                            log_event(logger, logging.INFO, "notification_sent", context=message_context)
                        else:
                            log_event(logger, logging.INFO, "notification_skipped", context=message_context)
                    except(Exception) as error:
                        duration_ms = int((time.monotonic() - started_at) * 1000)
                        log_event(
                            logger,
                            logging.ERROR,
                            "message_failed",
                            context=message_context,
                            stage=stage,
                            duration_ms=duration_ms,
                            exc_info=True,
                        )
                    else:
                        duration_ms = int((time.monotonic() - started_at) * 1000)
                        log_event(
                            logger,
                            logging.INFO,
                            "message_completed",
                            context=message_context,
                            duration_ms=duration_ms,
                        )
                        last_id = message_id
                        rdb.set(LAST_ID_KEY.format(consumer_id=consumer_id), last_id)

                # simulate processing
                #time.sleep(random.randint(1, 3)) #TODO : todo: remove!
        #else:
            #print(f"No new messages after ID: {last_id}")
