import json
import typer
import random
import time
import logging
from enum import Enum
from utils import redisstreamdb
from utils.foidocumentserviceconfig import documentservice_stream_key
from rstreamio.message.schemas.redactionsummary import get_in_redactionsummary_msg
from services.redactionsummaryservice import redactionsummaryservice
from rstreamio.writer.zipperstreamwriter import zipperstreamwriter

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
        print("Reading stream...")
        messages = stream.read(last_id=last_id, block=BLOCK_TIME)
        print("*********** Messages ***********")
        print(messages)
        if messages:
            for _messages in messages:          
                # message_id is the random id created to identify the message
                # message is the actual data passed to the stream 
                message_id, message = _messages 
                print(f"processing {message_id}::{message}")
                if message is not None:
                    _message = json.dumps({str(key): str(value) for (key, value) in message.items()})
                    _message = _message.replace("b'","'").replace("'",'')
                    try:
                        
                        filestozip= redactionsummaryservice().processmessage(get_in_redactionsummary_msg(_message))
                        # print("\n$$Before zipping- after summary- updatedmessage:", filestozip)
                        # print("\n$$Before zipping- after summary- message:", message)
                        #message_dict = {key.decode('utf-8'): value.decode('utf-8') for key, value in message.items()}
                        #print("\n\n@@@@message_dict: ",message_dict)
                        # Update the 'filestozip' field
                        ####################################
                        msgjson= json.loads(_message)
                        filestozip_list = msgjson['filestozip']
                        #filestozip_list= str(filestozip) # Add a new file
                        filestozip_list = json.loads(filestozip_list)
                        print("####TYPE of filestozip : ####",type(filestozip_list))
                        filestozip_list=filestozip
                        # Convert the updated dictionary back to bytes
                        #updated_message_bytes = {key.encode('utf-8'): value.encode('utf-8') for key, value in message_dict.items()}
                        json_string = json.dumps(filestozip_list)
                        bytes_data = json_string.encode('utf-8')
                        msgjson['filestozip'] =bytes_data

                        filesto_list1=json.loads(msgjson['attributes'])[0]['files']
                        print("ddd",filesto_list1)
                        filesto_list=filesto_list1
                        filesto_list=filestozip
                        json_string_attr_files =json.dumps(filesto_list)
                        bytes_data1 = json_string_attr_files.encode('utf-8')
                        attributes_list = json.loads(msgjson['attributes'])
                        attributes_list[0]['files'] = filestozip #bytes_data1
                        print("\n\nattributes_list: ",attributes_list)
                        msgjson['attributes'] = json.dumps(attributes_list)

                        # print("bytes_data",bytes_data1)
                        # print("LLLLLLL:",json.loads(msgjson['attributes'])[0]['files'])
                        # print("LLdsf:",msgjson['attributes'])
                        #json.loads(msgjson['attributes'])[0]['files']=bytes_data1
                        print("updated_message_bytes:",msgjson)
                        ############################################
                        zipperstreamwriter().sendmessage(msgjson)
                    except(Exception) as error: 
                        logging.exception(error)       
                    # simulate processing
                time.sleep(random.randint(1, 3)) #TODO : todo: remove!
                last_id = message_id
                rdb.set(LAST_ID_KEY.format(consumer_id=consumer_id), last_id)
                print(f"finished processing {message_id}")
        else:
            print(f"No new messages after ID: {last_id}")