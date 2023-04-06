import psycopg2
import logging
from config import pdfstitch_db_user,pdfstitch_db_port,pdfstitch_db_host,pdfstitch_db_name,pdfstitch_db_password

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
            if retry > 3:
                logging.error("Error in connecting DB.")
                logging.error(error)
                raise
            print("DB Connection retry = ", retry)
            retry += 1
            continue
