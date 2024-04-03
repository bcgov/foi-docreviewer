import os
import logging
import requests

from dotenv import load_dotenv

load_dotenv()


redishost = os.getenv("REDIS_HOST")
redisport = os.getenv("REDIS_PORT")
redispassword = os.getenv("REDIS_PASSWORD")
pagecalculator_stream_key = os.getenv("PAGECALCULATOR_STREAM_KEY")

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