import redis
import sys
import logging
from typing import List
from utils.foidocumentserviceconfig import redishost, redisport, redispassword

# Redis Connection
try:
    r = redis.Redis(
        host=str(redishost), 
        port=str(redisport), 
        db=0,
        password=str(redispassword),
        decode_responses=False # Crucial: Keep message content as bytes
    )
    r.ping()
    redisstreamdbnew = r 
    logging.info("Redis-py client initialized successfully.")
except Exception as e:
    logging.error(f"Failed to initialize redis-py client: {e}")
    sys.exit(1)


# Stream Class Wrapper
# translates the Walrus methods used into the native redis-py commands.
class Stream:
    def __init__(self, stream_key: str):
        self.stream_key = stream_key

    def create_group(self, groupname: str, start_id: str, ignore_exists: bool = False):
        """Wraps r.xgroup_create()"""
        try:
            redisstreamdbnew.xgroup_create(
                name=self.stream_key, 
                groupname=groupname, 
                id=start_id, 
                mkstream=True
            )
        except redis.exceptions.ResponseError as e:
            if ignore_exists and 'BUSYGROUP' in str(e):
                # Ignore the error if it's the group already exists error (BUSYGROUP)
                pass
            else:
                raise

    def autoclaim(self, groupname: str, consumername: str, min_idle_time: int, start_id: str, count: int) -> list:
        """Wraps r.xautoclaim() and returns only the list of messages."""
        # XAUTOCLAIM returns: [cursor, [ [msg_id, {field:value}], ... ], [deleted_ids, ...]]
        # We only need the middle list (index 1) which contains the messages.
        response = redisstreamdbnew.xautoclaim(
            self.stream_key, 
            groupname, 
            consumername, 
            min_idle_time, 
            start_id=start_id, 
            count=count
        )
        return response[1] if response and len(response) > 1 else []

    def read_group(self, groupname: str, consumername: str, count: int, block: int, start_id: str) -> list:
        """Wraps r.xreadgroup() and returns a simple list of messages."""
        
        # r.xreadgroup expects a dictionary of {stream_key: ID_to_start_from}
        read_response = redisstreamdbnew.xreadgroup(
            groupname, 
            consumername, 
            {self.stream_key: start_id}, 
            count=count, 
            block=block
        )

        # The structure is complex: [ [stream_key, [ [msg_id, {field:value}], ... ] ] ]
        # We simplify it to return a list of [message_id, message] tuples.
        if read_response and len(read_response) > 0 and len(read_response[0]) > 1:
            # read_response[0] is the [stream_key, messages] pair
            # read_response[0][1] is the list of messages
            return read_response[0][1]
        return []

    def ack(self, groupname: str, message_ids: List[bytes]):
        """Wraps r.xack()"""
        redisstreamdbnew.xack(self.stream_key, groupname, *message_ids)

# Attach the Stream class to the exported redis client so the main script can call rdb.Stream()
setattr(redisstreamdbnew, 'Stream', Stream)