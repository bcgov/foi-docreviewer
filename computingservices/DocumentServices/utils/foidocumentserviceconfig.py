import os
import logging
import requests

from dotenv import load_dotenv

load_dotenv()


redishost = os.getenv("REDIS_HOST")
redisport = os.getenv("REDIS_PORT")
redispassword = os.getenv("REDIS_PASSWORD")
documentservice_stream_key = os.getenv("DOCUMENTSERVICE_STREAM_KEY")
pagecalculator_stream_key = os.getenv("PAGECALCULATOR_STREAM_KEY")

docservice_db_host = os.getenv("DOCUMENTSERVICE_DB_HOST")
docservice_db_name = os.getenv("DOCUMENTSERVICE_DB_NAME")
docservice_db_port = os.getenv("DOCUMENTSERVICE_DB_PORT")
docservice_db_user = os.getenv("DOCUMENTSERVICE_DB_USER")
docservice_db_password = os.getenv("DOCUMENTSERVICE_DB_PASSWORD")

docservice_s3_host = os.getenv("DOCUMENTSERVICE_S3_HOST")
docservice_s3_region = os.getenv("DOCUMENTSERVICE_S3_REGION")
docservice_s3_service = os.getenv("DOCUMENTSERVICE_S3_SERVICE")
docservice_s3_env = os.getenv("DOCUMENTSERVICE_S3_ENV")


# Zipper stream config
zipperredishost = os.getenv("ZIPPER_REDIS_HOST")
zipperredisport = os.getenv("ZIPPER_REDIS_PORT")
zipperredispassword = os.getenv("ZIPPER_REDIS_PASSWORD")
zipper_stream_key = os.getenv("ZIPPER_STREAM_KEY")
