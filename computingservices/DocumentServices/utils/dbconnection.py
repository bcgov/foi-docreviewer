import psycopg2
from . import docservice_db_user,docservice_db_port,docservice_db_host,docservice_db_name,docservice_db_password

def getdbconnection():
    conn = psycopg2.connect(
        host=docservice_db_host,
        database=docservice_db_name,
        user=docservice_db_user,
        password=docservice_db_password,port=docservice_db_port)
    return conn    