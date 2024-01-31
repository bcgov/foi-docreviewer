import psycopg2
from . import docservice_db_user,docservice_db_port,docservice_db_host,docservice_db_name,docservice_db_password,foi_db_user,foi_db_port,foi_db_host,foi_db_name,foi_db_password

def getdbconnection():
    conn = psycopg2.connect(
        host=docservice_db_host,
        database=docservice_db_name,
        user=docservice_db_user,
        password=docservice_db_password,port=docservice_db_port)
    return conn

def getfoidbconnection():
    conn = psycopg2.connect(
        host=foi_db_host,
        database=foi_db_name,
        user=foi_db_user,
        password=foi_db_password,port=foi_db_port)
    return conn