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

dedupe_s3_host = os.getenv('DEDUPE_S3_HOST')
dedupe_s3_host = os.getenv('DEDUPE_S3_HOST')
dedupe_s3_region = os.getenv('DEDUPE_S3_REGION')
dedupe_s3_service = os.getenv('DEDUPE_S3_SERVICE')
dedupe_s3_env = os.getenv('DEDUPE_S3_ENV')

request_management_api = os.getenv('DEDUPE_REQUEST_MANAGEMENT_API')

#Notification stream config
notification_stream_key = os.getenv('NOTIFICATION_STREAM_KEY')