from . import conn
import psycopg2
from psycopg2 import sql
import json

def getcredentialsbybcgovcode(bcgovcode):
    try:

        cur = conn.cursor()

        _sql = sql.SQL("SELECT  attributes FROM {0} WHERE bucket='{1}'and category='Records'".format('public."DocumentPathMapper"','{0}-dev'.format(bcgovcode.lower())))
        cur.execute(_sql)
        attributes = cur.fetchone()
        print(json.dumps(attributes[0]))
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()
            print('Database connection closed.') 


