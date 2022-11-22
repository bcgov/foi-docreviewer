import os

from dotenv import load_dotenv
load_dotenv()


redishost = os.getenv('REDIS_HOST') 
redisport = os.getenv('REDIS_PORT')
redispassword = os.getenv('REDIS_PASSWORD')

dedupe_stream_key = os.getenv('DEDUPE_STREAM_KEY')