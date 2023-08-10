import os

from dotenv import load_dotenv
load_dotenv()


redishost = os.getenv('REDIS_HOST') 
redisport = os.getenv('REDIS_PORT')
redispassword = os.getenv('REDIS_PASSWORD')
zipper_stream_key = os.getenv('ZIPPER_STREAM_KEY')

db_host = os.getenv('DB_HOST')
db_name = os.getenv('DB_NAME')
db_port = os.getenv('DB_PORT')
db_user = os.getenv('DB_USER')
db_password = os.getenv('DB_PASSWORD')

s3_host = os.getenv('S3_HOST')
s3_host = os.getenv('S3_HOST')
s3_region = os.getenv('S3_REGION')
s3_service = os.getenv('S3_SERVICE')
s3_env = os.getenv('S3_ENV')

#Notification stream config
notification_stream_key = os.getenv('NOTIFICATION_STREAM_KEY')
notification_redis_host = os.getenv('NOTIFICATION_REDIS_HOST')
notification_redis_password = os.getenv('NOTIFICATION_REDIS_PASSWORD')
notification_redis_port = os.getenv('NOTIFICATION_REDIS_PORT')

failureattempt = os.getenv('FAILUREATTEMPT', 3)