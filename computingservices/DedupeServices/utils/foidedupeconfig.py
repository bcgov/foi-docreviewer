import os
import logging
import requests

from dotenv import load_dotenv

load_dotenv()


redishost = os.getenv("REDIS_HOST")
redisport = os.getenv("REDIS_PORT")
redispassword = os.getenv("REDIS_PASSWORD")
dedupe_stream_key = os.getenv("DEDUPE_STREAM_KEY")

dedupe_db_host = os.getenv("DEDUPE_DB_HOST")
dedupe_db_name = os.getenv("DEDUPE_DB_NAME")
dedupe_db_port = os.getenv("DEDUPE_DB_PORT")
dedupe_db_user = os.getenv("DEDUPE_DB_USER")
dedupe_db_password = os.getenv("DEDUPE_DB_PASSWORD")

dedupe_s3_host = os.getenv("DEDUPE_S3_HOST")
dedupe_s3_region = os.getenv("DEDUPE_S3_REGION")
dedupe_s3_service = os.getenv("DEDUPE_S3_SERVICE")
dedupe_s3_env = os.getenv("DEDUPE_S3_ENV")

request_management_api = os.getenv("DEDUPE_REQUEST_MANAGEMENT_API")
record_formats_path = os.getenv("DEDUPE_RECORD_FORMATS")

pagecalculatorredishost = os.getenv('REDIS_HOST') 
pagecalculatorredispassword = os.getenv('REDIS_PASSWORD')
pagecalculatorredisport = os.getenv('REDIS_PORT')
pagecalculatorstreamkey = os.getenv('PAGECALCULATOR_STREAM_KEY')
health_check_interval = os.getenv('HEALTH_CHECK_INTERVAL', 15)

compressionredishost= os.getenv('REDIS_HOST')
compressionredispassword= os.getenv('REDIS_PASSWORD')
compressionredisport= os.getenv('REDIS_PORT')
compressionstreamkey= os.getenv('COMPRESSION_STREAM_KEY')

try:
    response = requests.request(
        method="GET",
        url=record_formats_path,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    file_conversion_types = response.json()["conversion"]
    dedupe_file_types = response.json()["dedupe"]
    nonredactable_file_types = response.json()["nonredactable"]
except Exception as err:
    logging.error("Unable to retrieve record upload formats from S3")
    logging.error(err)
    file_conversion_types = [".doc", ".docx", ".xls", ".xlsx", ".msg"]

# Notification stream config
notification_stream_key = os.getenv("NOTIFICATION_STREAM_KEY")
