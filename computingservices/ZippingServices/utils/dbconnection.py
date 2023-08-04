import psycopg2
from . import db_user,db_port,db_host,db_name,db_password

def getdbconnection():
    conn = psycopg2.connect(
        host=db_host,
        database=db_name,
        user=db_user,
        password=db_password,port=db_port)
    return conn    