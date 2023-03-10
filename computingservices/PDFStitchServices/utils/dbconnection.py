import psycopg2
from . import pdfstitch_db_user,pdfstitch_db_port,pdfstitch_db_host,pdfstitch_db_name,pdfstitch_db_password

def getdbconnection():
    conn = psycopg2.connect(
        host=pdfstitch_db_host,
        database=pdfstitch_db_name,
        user=pdfstitch_db_user,
        password=pdfstitch_db_password,port=pdfstitch_db_port)
    return conn