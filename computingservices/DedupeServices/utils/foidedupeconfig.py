import os

from dotenv import load_dotenv
load_dotenv()


redishost = os.getenv('REDIS_HOST') 
redisport = os.getenv('REDIS_PORT')
redispassword = os.getenv('REDIS_PASSWORD')
dedupe_stream_key = os.getenv('DEDUPE_STREAM_KEY')

dedupe_db_host = os.getenv('DEDUPE_DB_HOST')
dedupe_db_name = os.getenv('DEDUPE_DB_NAME')
dedupe_db_port = os.getenv('DEDUPE_DB_PORT')
dedupe_db_user = os.getenv('DEDUPE_DB_USER')
dedupe_db_password = os.getenv('DEDUPE_DB_PASSWORD')
