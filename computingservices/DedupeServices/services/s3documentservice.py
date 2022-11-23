from . import getdbconnection
from utils import dedupe_db_user,dedupe_db_port,dedupe_db_host,dedupe_db_name,dedupe_db_password
import psycopg2
from psycopg2 import sql
import json


def getcredentialsbybcgovcode(bcgovcode):
    _conn = getdbconnection()
    try:
                              
        cur = _conn.cursor()
        _sql = sql.SQL("SELECT  attributes FROM {0} WHERE bucket='{1}'and category='Records'".format('public."DocumentPathMapper"','{0}-dev'.format(bcgovcode.lower())))
        cur.execute(_sql)
        attributes = cur.fetchone()
        print("##############Attributes#######################")
        print(json.dumps(attributes))
        print(json.dumps(attributes[0]))
        print("#####################################")
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if _conn is not None:
            _conn.close()
            print('Database connection closed.') 


