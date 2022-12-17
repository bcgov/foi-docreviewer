from . import getdbconnection
from models import dedupeproducermessage
from datetime import datetime
import json

def savedocumentdetails(dedupeproducermessage, hashcode):
    try:
        conn = getdbconnection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO public."Documents" (version, \
        filename, filepath,foiministryrequestid,createdby,created_at,statusid) VALUES(%s::integer, %s, %s,%s::integer,%s,%s,%s::integer) RETURNING documentid;', (1, dedupeproducermessage.filename, dedupeproducermessage.s3filepath,
        dedupeproducermessage.ministryrequestid,'{"user":"dedupeservice"}',datetime.now(),1))
        conn.commit()
        id_of_new_row = cursor.fetchone()

        cursor.execute('INSERT INTO public."DocumentHashCodes" (documentid, \
        rank1hash,created_at) VALUES(%s::integer, %s,%s)', (id_of_new_row, hashcode,datetime.now()))
        conn.commit()


        cursor.execute('INSERT INTO public."DocumentTags"(\
	    documentid, documentversion, tag, createdby, created_at) VALUES (%s::integer, %s::integer, %s,%s,%s)',(id_of_new_row,1,dedupeproducermessage.attributes,'{"user":"dedupeservice"}',datetime.now()))
        conn.commit()

        # combine list of divisions and save to original tag
        cursor.execute('''select d.documentid, dt.tag from public."DocumentHashCodes" hc
            join public."Documents" d on hc.documentid = d.documentid
            join public."DocumentTags" dt on dt.documentid = d.documentid
            where hc.rank1hash = %s
            order by hc.created_at asc limit 1''',
            (hashcode,)
        )
        (originalid, attributes) = cursor.fetchone()
        messageattributes = json.loads(dedupeproducermessage.attributes)
        divid = lambda div : div['divisionid']
        divobj = lambda divid : {"divisionid" : divid}
        attributes['divisions'] = list(map(divobj, set(map(divid, attributes['divisions'])).union(set(map(divid, messageattributes['divisions'])))))

        cursor.execute('''update public."DocumentTags" set tag = %s where documentid = %s''', (json.dumps(attributes), originalid))
        conn.commit()

        cursor.close()
        conn.close()
        return True
    except(Exception) as error:
        print(error)
        return False



