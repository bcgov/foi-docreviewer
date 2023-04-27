import psycopg2
import logging
from config import pdfstitch_db_user,pdfstitch_db_port,pdfstitch_db_host,pdfstitch_db_name,pdfstitch_db_password, pdfstitch_failureattempt

def getdbconnection():
    retry = 0
    while True:
        try:
            conn = psycopg2.connect(
                host=pdfstitch_db_host,
                database=pdfstitch_db_name,
                user=pdfstitch_db_user,
                password=pdfstitch_db_password,port=pdfstitch_db_port)
            return conn
        except psycopg2.Error as error:            
            if retry > int(pdfstitch_failureattempt):
                logging.error("Error in connecting DB.")
                logging.error(error)
                raise
            retry += 1
            continue
