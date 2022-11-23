import psycopg2
from . import dedupe_db_user,dedupe_db_port,dedupe_db_host,dedupe_db_name,dedupe_db_password

conn = psycopg2.connect(
    host=dedupe_db_host,
    database=dedupe_db_name,
    user=dedupe_db_user,
    password=dedupe_db_password,port=dedupe_db_port)