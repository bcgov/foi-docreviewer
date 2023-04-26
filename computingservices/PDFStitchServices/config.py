"""Manage profile specific variables
"""
import os

from dotenv import load_dotenv
load_dotenv()


redishost = os.getenv('REDIS_HOST') 
redisport = os.getenv('REDIS_PORT')
redispassword = os.getenv('REDIS_PASSWORD')

notification_redishost = os.getenv('NOTIFICATION_REDIS_HOST') 
notification_redisport = os.getenv('NOTIFICATION_REDIS_PORT')
notification_redispassword = os.getenv('NOTIFICATION_REDIS_PASSWORD')

pdfstitch_db_host = os.getenv('PDFSTITCH_DB_HOST')
pdfstitch_db_name = os.getenv('PDFSTITCH_DB_NAME')
pdfstitch_db_port = os.getenv('PDFSTITCH_DB_PORT')
pdfstitch_db_user = os.getenv('PDFSTITCH_DB_USER')
pdfstitch_db_password = os.getenv('PDFSTITCH_DB_PASSWORD')

pdfstitch_s3_host = os.getenv('PDFSTITCH_S3_HOST')
pdfstitch_s3_region = os.getenv('PDFSTITCH_S3_REGION')
pdfstitch_s3_service = os.getenv('PDFSTITCH_S3_SERVICE')
pdfstitch_s3_env = os.getenv('PDFSTITCH_S3_ENV')
pdfstitch_s3_bucket = os.getenv('PDFSTITCH_S3_BUCKET')

#stream config
notification_stream_key = os.getenv('NOTIFICATION_STREAM_KEY')
division_pdf_stitch_stream_key = os.getenv('DIVISION_PDF_STITCH_STREAM_KEY')
division_blob_stitch_stream_key = os.getenv('DIVISION_BLOB_STITCH_STREAM_KEY')

division_stitch_folder_path = os.getenv('DIVISION_STITCH_FOLDER_PATH')
error_flag = os.getenv('ERROR_FLAG')

pdfstitch_failureattempt = os.getenv('PDF_STITCH_FAILUREATTEMPT', 3)

numbering_enabled = os.getenv('NUMBERING_ENABLED')
zip_enabled = os.getenv('ZIP_ENABLED')

notification_enabled = os.getenv('NOTIFICATION_ENABLED')

