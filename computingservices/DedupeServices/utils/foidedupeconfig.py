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
compression_messaging_mode = os.getenv('COMPRESSION_MESSAGING_MODE', 'legacy')
messaging_stream_prefix = os.getenv('MESSAGING_STREAM_PREFIX', 'foi')
compression_topic = os.getenv('COMPRESSION_TOPIC')
compression_workload = os.getenv('COMPRESSION_WORKLOAD')


def _positive_int(name, default):
    raw = os.getenv(name)
    try:
        value = default if raw is None else int(raw)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a positive integer") from error

    if value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


dedupe_consumer_group = os.getenv("DEDUPE_CONSUMER_GROUP", "dedupe")
dedupe_consumer_name = os.getenv("DEDUPE_CONSUMER_NAME")
dedupe_consumer_batch_size = _positive_int("DEDUPE_CONSUMER_BATCH_SIZE", 10)
dedupe_consumer_block_ms = _positive_int("DEDUPE_CONSUMER_BLOCK_MS", 5000)
dedupe_consumer_max_retries = _positive_int("DEDUPE_CONSUMER_MAX_RETRIES", 5)
dedupe_consumer_retry_backoff_ms = _positive_int(
    "DEDUPE_CONSUMER_RETRY_BACKOFF_MS", 250
)
dedupe_consumer_claim_min_idle_ms = _positive_int(
    "DEDUPE_CONSUMER_CLAIM_MIN_IDLE_MS", 60000
)
dedupe_dlq_stream = os.getenv("DEDUPE_DLQ_STREAM", "foi:dedupe.dlq")
dedupe_dlq_maxlen = _positive_int("DEDUPE_DLQ_MAXLEN", 10000)

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
