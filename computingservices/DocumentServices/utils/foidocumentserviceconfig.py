import os
import logging
import requests

from dotenv import load_dotenv

load_dotenv()


redishost = os.getenv("REDIS_HOST")
redisport = os.getenv("REDIS_PORT")
redispassword = os.getenv("REDIS_PASSWORD")

documentservice_stream_key = os.getenv("DOCUMENTSERVICE_STREAM_KEY")
documentservice_block_time = int(os.getenv("DOCUMENTSERVICE_BLOCK_TIME", 5000))
documentservice_group_name = os.getenv("DOCUMENTSERVICE_GROUP_NAME")
documentservice_consumer_name_prefix = os.getenv("DOCUMENTSERVICE_CONSUMER_NAME_PREFIX")
documentservice_batch_size = int(os.getenv("DOCUMENTSERVICE_BATCH_SIZE", 1))
# Number of messages to read in one batch, recommended to be 5-10
# Set to 1, becasese some documents can be large and take time to process
documentservice_pod_name = os.environ.get('HOSTNAME')

docservice_db_host = os.getenv("DOCUMENTSERVICE_DB_HOST")
docservice_db_name = os.getenv("DOCUMENTSERVICE_DB_NAME")
docservice_db_port = os.getenv("DOCUMENTSERVICE_DB_PORT")
docservice_db_user = os.getenv("DOCUMENTSERVICE_DB_USER")
docservice_db_password = os.getenv("DOCUMENTSERVICE_DB_PASSWORD")

foi_db_host = os.getenv("FOI_DB_HOST")
foi_db_name = os.getenv("FOI_DB_NAME")
foi_db_port = os.getenv("FOI_DB_PORT")
foi_db_user = os.getenv("FOI_DB_USER")
foi_db_password = os.getenv("FOI_DB_PASSWORD")

docservice_s3_host = os.getenv("DOCUMENTSERVICE_S3_HOST")
docservice_s3_region = os.getenv("DOCUMENTSERVICE_S3_REGION")
docservice_s3_service = os.getenv("DOCUMENTSERVICE_S3_SERVICE")
docservice_s3_env = os.getenv("DOCUMENTSERVICE_S3_ENV")

docservice_failureattempt = os.getenv('DOCUMENTSERVICE_FAILUREATTEMPT', 3)


# Zipper stream config
zipperredishost = os.getenv("ZIPPER_REDIS_HOST")
zipperredisport = os.getenv("ZIPPER_REDIS_PORT")
zipperredispassword = os.getenv("ZIPPER_REDIS_PASSWORD")
zipper_stream_key = os.getenv("ZIPPER_STREAM_KEY")


cdogs_base_url = os.getenv("CDOGS_BASE_URL")
cdogs_token_url = os.getenv("CDOGS_TOKEN_URL")
cdogs_service_client = os.getenv("CDOGS_SERVICE_CLIENT")
cdogs_service_client_secret = os.getenv("CDOGS_SERVICE_CLIENT_SECRET")
