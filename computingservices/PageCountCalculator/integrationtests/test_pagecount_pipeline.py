"""Opt-in real packaged worker, private Redis, and separate PostgreSQL databases."""
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import uuid

import psycopg2
from psycopg2.extras import Json
import pytest
from redis import Redis

pytestmark = pytest.mark.skipif(os.getenv("RUN_PAGECOUNT_INTEGRATION") != "1",
                               reason="Use integrationtests/run-isolated.sh")


def poll(predicate, timeout=25):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError("Timed out waiting for persisted worker result")


class Pipeline:
    def __init__(self):
        self.redis = Redis(host=os.environ["REDIS_HOST"], port=int(os.environ["REDIS_PORT"]),
                           password=os.environ["REDIS_PASSWORD"])
        owner = os.environ["PAGECOUNT_TEST_INSTANCE"]
        assert owner.startswith("pagecount-it-")
        assert self.redis.get("pagecount_it_owner") == owner.encode()
        assert self.redis.keys() == [b"pagecount_it_owner"], "Refuse nonempty Redis"
        self.connections = []
        for prefix, expected in (("DOCUMENTSERVICE", "pagecount_documents_it_disposable"),
                                 ("FOI", "pagecount_foi_it_disposable")):
            assert os.environ[f"{prefix}_DB_NAME"] == expected
            connection = psycopg2.connect(**{
                key: os.environ[f"{prefix}_DB_{setting}"] for key, setting in
                (("host", "HOST"), ("port", "PORT"), ("dbname", "NAME"),
                 ("user", "USER"), ("password", "PASSWORD"))})
            connection.autocommit = True
            with connection.cursor() as cursor:
                cursor.execute('SELECT token FROM pagecount_it_owner')
                assert cursor.fetchall() == [(owner,)], "Refuse unowned database"
            self.connections.append(connection)
        self.doc, self.foi = self.connections
        for conn, name in ((self.doc, "docreviewer.pgsql"), (self.foi, "foi.pgsql")):
            with conn.cursor() as cursor:
                cursor.execute(Path(__file__).with_name(name).read_text())
                role = "pagecount_doc" if conn is self.doc else "pagecount_foi"
                cursor.execute(f'GRANT USAGE ON SCHEMA public TO {role}; '
                               f'GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO {role}; '
                               f'GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO {role}')
        self.process = None
        self.log = tempfile.TemporaryFile(mode="w+")
        self.stream = "pagecount-it-" + uuid.uuid4().hex
        self.max_rss = 0

    def sql(self, connection, query, args=(), fetch=False):
        with connection.cursor() as cursor:
            cursor.execute(query, args)
            return cursor.fetchall() if fetch else None

    def start(self):
        self.process = subprocess.Popen(["/bin/sh", "./entrypoint.sh"],
            env={**os.environ, "PAGECALCULATOR_STREAM_KEY": self.stream,
                 "DOCUMENTSERVICE_DB_USER": "pagecount_doc", "FOI_DB_USER": "pagecount_foi"},
            stdout=self.log, stderr=self.log, start_new_session=True)
        poll(lambda: self.process.poll() is None and any(
            c.get("cmd") == "xread" and "b" in c.get("flags", "")
            for c in self.redis.client_list()))
        # Sample the actual Python child, rather than only its shell parent.
        children = Path(f"/proc/{self.process.pid}/task/{self.process.pid}/children").read_text().split()
        for child in children:
            for line in Path(f"/proc/{child}/status").read_text().splitlines():
                if line.startswith("VmHWM:"):
                    self.max_rss = max(self.max_rss, int(line.split()[1]))

    def stop(self):
        if self.process is not None:
            os.killpg(self.process.pid, signal.SIGTERM)
            self.process.wait(timeout=10)
            self.process = None

    def publish(self, job, **fields):
        return self.redis.xadd(self.stream, {"jobid": str(job), "ministryrequestid": "41",
            "documentmasterid": "1", "filename": "synthetic.pdf", "createdby": "synthetic",
            "trigger": "dedupe", **fields})

    def finish(self, identifier):
        poll(lambda: self.redis.get("$:lastid") == identifier)
        assert self.redis.xrange(self.stream, identifier, identifier), "Reader retains input entries"
        assert self.process.poll() is None

    def jobs(self, job):
        return self.sql(self.doc, 'SELECT version,status,pagecount,inputmessage,message FROM "PageCalculatorJob" '
                        'WHERE pagecalculatorjobid=%s ORDER BY version', (job,), True)

    def request(self):
        return self.sql(self.foi, 'SELECT version,recordspagecount,updatedby,updated_at FROM "FOIMinistryRequests" '
                        'ORDER BY version', fetch=True)

    def seed_request(self, count="9"):
        self.sql(self.foi, 'INSERT INTO "FOIMinistryRequests" VALUES (41,1,false,\'123\',NULL,NULL),'
                 '(41,2,true,%s,NULL,NULL)', (count,))

    def document(self, identifier, pages, parent=None, hash_=None, active=True, **attributes):
        self.sql(self.doc, 'INSERT INTO "DocumentMaster" (documentmasterid,filepath,ministryrequestid,'
                 'recordid,parentid,createdby) VALUES (%s,%s,41,%s,%s,\'synthetic\')',
                 (identifier, f"synthetic/{identifier}.pdf", identifier if parent is None else None, parent))
        self.sql(self.doc, 'INSERT INTO "DocumentAttributes" (documentmasterid,attributes,isactive) VALUES (%s,%s,%s)',
                 (identifier, Json({"incompatible": False, "lastmodified": "2020-01-15", **attributes}), active))
        self.sql(self.doc, 'INSERT INTO "Documents" VALUES (%s,1,%s,41,%s,%s)',
                 (identifier, identifier, f"{identifier}.pdf", pages))
        self.sql(self.doc, 'INSERT INTO "DocumentHashCodes" VALUES (%s,%s)', (identifier, hash_ or str(identifier)))


@pytest.fixture
def pipeline():
    p = Pipeline()
    started = time.monotonic()
    try:
        yield p
    finally:
        p.stop()
        p.log.seek(0)
        print(p.log.read())
        print(f"CASE seconds={time.monotonic()-started:.3f} sampled_peak_rss_kib={p.max_rss}")
        p.log.close()
        for conn in p.connections:
            conn.close()
        # Remove only this fixture's tables after the worker stops; retain ownership.
        for prefix in ("DOCUMENTSERVICE", "FOI"):
            conn = psycopg2.connect(host=os.environ[f"{prefix}_DB_HOST"], port=os.environ[f"{prefix}_DB_PORT"],
                dbname=os.environ[f"{prefix}_DB_NAME"], user=os.environ[f"{prefix}_DB_USER"],
                password=os.environ[f"{prefix}_DB_PASSWORD"])
            conn.autocommit = True
            with conn.cursor() as cursor:
                if prefix == "DOCUMENTSERVICE":
                    cursor.execute('DROP TABLE "DocumentMaster", "DocumentAttributes", "Documents", '
                                   '"DocumentHashCodes", "DocumentDeleted", "DeduplicationJob", '
                                   '"PageCalculatorJob" CASCADE; DROP FUNCTION IF EXISTS reject_end()')
                else:
                    cursor.execute('DROP TABLE "FOIMinistryRequests" CASCADE; '
                                   'DROP FUNCTION IF EXISTS reject_update()')
            conn.close()
        p.redis.delete(p.stream, "$:lastid")


def test_metadata_persistence_recalculation_and_saved_cursor(pipeline):
    p = pipeline
    p.seed_request()
    for args in ((1,3,None,"parent"), (2,2,1,"attachment"), (3,4,2,None),
                 (4,2,1,"attachment"), (10,3,None,"parent"), (11,99,10,None)):
        p.document(*args)
    p.document(20,99,isportfolio=True)
    p.document(30,99,incompatible=True)
    p.document(40,99,active=False)
    p.document(50,99)
    p.sql(p.doc, 'INSERT INTO "DocumentDeleted" VALUES (\'synthetic/50\',41)')
    historical = p.publish(100)
    p.start()
    p.finish(p.publish(101, pagecount="777"))
    assert p.jobs(100) == []
    rows = p.jobs(101)
    assert [(r[0],r[1]) for r in rows] == [(2,"started"),(3,"completed")]
    assert rows[1][2] == {"prevpagecount": "9", "calculatedpagecount": 9}
    assert rows[1][3]["trigger"] == "dedupe"
    request = p.request()
    assert request[0] == (1,"123",None,None)
    assert request[1][:3] == (2,"9","synthetic")
    assert request[1][3] is not None
    # Same job replay remains non-idempotent for FOI updates; history conflicts
    # retain the original rows. Characterize rather than repair this policy.
    p.finish(p.publish(101))
    assert p.jobs(101) == rows
    assert p.request()[1][3] > request[1][3]
    p.stop()
    p.sql(p.doc, 'UPDATE "Documents" SET pagecount=6 WHERE documentid=3')
    queued = p.publish(102)
    p.start()
    p.finish(queued)
    assert p.jobs(100) == []
    assert p.redis.xrange(p.stream, historical, historical)
    assert p.jobs(102)[1][2] == {"prevpagecount": "9", "calculatedpagecount": 11}
    assert p.request()[1][:3] == (2,"11","synthetic")


def test_null_shortcut_text_zero_and_wire_filenames(pipeline):
    p = pipeline
    p.seed_request(None)
    p.document(1,3)
    p.start()
    p.finish(p.publish(201, pagecount="7", filename="résumé.pdf"))
    assert p.request()[1][:3] == (2,"7","synthetic")
    rows = p.jobs(201)
    assert rows[1][2] == {"prevpagecount": None, "calculatedpagecount": 7}
    # Legacy byte->str conversion persists escaped bytes rather than Unicode.
    assert rows[1][3]["filename"] == r"r\xc3\xa9sum\xc3\xa9.pdf"
    p.sql(p.foi, 'UPDATE "FOIMinistryRequests" SET recordspagecount=\'0\' WHERE isactive')
    p.finish(p.publish(202, pagecount="777"))
    assert p.jobs(202)[1][2] == {"prevpagecount": "0", "calculatedpagecount": 3}
    assert p.request()[1][1] == "3"
    p.finish(p.publish(203, filename="O'Brien.pdf"))
    assert p.jobs(203)[1][3]["filename"] == 'b"OBrien.pdf"'


def test_database_failures_malformed_messages_and_partial_commit(pipeline):
    p = pipeline
    p.seed_request()
    p.document(1,3)
    p.start()
    p.sql(p.foi, '''CREATE FUNCTION reject_update() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'synthetic request update failure'; END $$;
        CREATE TRIGGER fail_update BEFORE UPDATE ON "FOIMinistryRequests"
        FOR EACH ROW EXECUTE FUNCTION reject_update()''')
    p.finish(p.publish(301))
    assert [(r[0],r[1],r[2]) for r in p.jobs(301)] == [(2,"started",None),(3,"completed",None)]
    assert p.request()[1] == (2,"9",None,None)
    p.sql(p.foi, 'DROP TRIGGER fail_update ON "FOIMinistryRequests"')
    p.sql(p.doc, 'ALTER TABLE "DocumentAttributes" RENAME TO "HiddenAttributes"')
    p.finish(p.publish(302))
    assert p.jobs(302)[1][1:3] == ("completed",None)
    assert p.request()[1] == (2,"9",None,None)
    p.sql(p.doc, 'ALTER TABLE "HiddenAttributes" RENAME TO "DocumentAttributes"')
    p.finish(p.publish(303, pagecount="invalid"))
    assert p.jobs(303) == []
    assert p.request()[1] == (2,"9",None,None)
    p.sql(p.doc, '''CREATE FUNCTION reject_end() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN IF NEW.version=3 THEN RAISE EXCEPTION 'synthetic job end failure'; END IF; RETURN NEW; END $$;
        CREATE TRIGGER fail_end BEFORE INSERT ON "PageCalculatorJob"
        FOR EACH ROW EXECUTE FUNCTION reject_end()''')
    p.finish(p.publish(304))
    assert [(r[0],r[1]) for r in p.jobs(304)] == [(2,"started")]
    assert p.request()[1][:3] == (2,"3","synthetic")
