"""Opt-in, real worker/Redis/PostgreSQL/HTTPS S3 round trips.

Use run-isolated.sh. No application imports or offline conftest configuration here.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import uuid

import boto3
import fitz
import psycopg2
import pytest
import redis


def wait_for(check, description, timeout=45):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        time.sleep(0.1)
    pytest.fail("Timed out waiting for " + description)


@pytest.fixture
def pipeline(tmp_path):
    if os.getenv("RUN_PDFSTITCH_INTEGRATION") != "1":
        pytest.fail("Opt-in required: use integrationtests/run-isolated.sh with disposable services")
    env = os.environ.copy()
    assert env["PDFSTITCH_DB_NAME"].startswith("pdfstitch_it_")
    token = uuid.uuid4().hex
    env.update({"DIVISION_PDF_STITCH_STREAM_KEY": "pdfstitch-it:" + token + ":input",
                "ZIPPER_STREAM_KEY": "pdfstitch-it:" + token + ":zipper",
                "NOTIFICATION_STREAM_KEY": "pdfstitch-it:" + token + ":notification",
                "MESSAGE_BLOCK_TIME": "0", "NOTIFICATION_ENABLED": "True", "NUMBERING_ENABLED": "False",
                "DIVISION_STITCH_FOLDER_PATH": "Stitched/divisionname", "TMPDIR": str(tmp_path)})
    rdb = redis.Redis(host=env["REDIS_HOST"], port=int(env["REDIS_PORT"]), password=env["REDIS_PASSWORD"])
    # The actual entrypoint uses a literal shared cursor name. Require proof
    # that this is the disposable Redis instance owned by run-isolated.sh.
    owner = env.get("PDFSTITCH_TEST_INSTANCE", "")
    assert owner.startswith("pdfstitch-it-")
    assert rdb.get("pdfstitch_it_owner") == owner.encode()
    assert rdb.dbsize() == 1, "Refusing Redis containing state other than the harness ownership marker"
    conn = psycopg2.connect(host=env["PDFSTITCH_DB_HOST"], port=env["PDFSTITCH_DB_PORT"],
                            dbname=env["PDFSTITCH_DB_NAME"], user=env["PDFSTITCH_DB_USER"], password=env["PDFSTITCH_DB_PASSWORD"])
    conn.autocommit = True
    s3 = boto3.client("s3", endpoint_url="https://" + env["PDFSTITCH_S3_HOST"],
                      aws_access_key_id=env["AWS_ACCESS_KEY_ID"], aws_secret_access_key=env["AWS_SECRET_ACCESS_KEY"],
                      region_name="us-east-1", verify=env["REQUESTS_CA_BUNDLE"])
    code = "s" + token[:12]
    bucket = code + "-it-e"
    s3.create_bucket(Bucket=bucket)
    with conn.cursor() as cur:
        # Only in a disposable database created by the harness. Not migrations.
        cur.execute('CREATE TABLE IF NOT EXISTS public."PDFStitchJob" (pdfstitchjobid integer, version integer, ministryrequestid integer, category text, inputfiles text, outputfiles text, status text, message text, createdby text, PRIMARY KEY (pdfstitchjobid, version))')
        cur.execute('CREATE TABLE IF NOT EXISTS public."DocumentPathMapper" (bucket text, category text, attributes text)')
        cur.execute('INSERT INTO public."DocumentPathMapper" VALUES (%s, %s, %s)',
                    (bucket, "Records", json.dumps({"s3accesskey": env["AWS_ACCESS_KEY_ID"], "s3secretkey": env["AWS_SECRET_ACCESS_KEY"]})))

    workers = []
    peak_kib = [0]
    peak_tmp_bytes = [0]

    def sample():
        peak_tmp_bytes[0] = max(peak_tmp_bytes[0], sum(p.stat().st_size for p in tmp_path.rglob("*") if p.is_file()))
        for worker, _ in workers:
            children = Path(f"/proc/{worker.pid}/task/{worker.pid}/children")
            pids = [str(worker.pid)] + (children.read_text().split() if children.exists() else [])
            for pid in pids:
                status = Path(f"/proc/{pid}/status")
                if status.exists():
                    for line in status.read_text().splitlines():
                        if line.startswith("VmHWM:"):
                            peak_kib[0] = max(peak_kib[0], int(line.split()[1]))

    def start():
        # Execute the literal shipped entrypoint, whose positional consumer is "$".
        log = tempfile.TemporaryFile()
        process = subprocess.Popen(["/bin/sh", "./entrypoint.sh"], env=env, stdout=log, stderr=log,
                                   start_new_session=True)
        workers.append((process, log))

        def ready():
            if process.poll() is not None:
                log.seek(0)
                pytest.fail("Worker exited before readiness: " + log.read().decode()[-2000:])
            sample()
            return any(client.get("cmd") == "xread" for client in rdb.client_list())

        wait_for(ready, "worker blocking in XREAD")

    def stop():
        import signal
        for process, log in workers:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=10)
            log.close()
        workers.clear()

    counter = [int(token[:6], 16) * 10]

    def enqueue(files, divisions=1):
        counter[0] += 1
        jobid = counter[0]
        attributes = [{"divisionname": "Division" + str(i), "divisionid": i + 1, "files": files} for i in range(divisions)]
        message = dict(jobid=str(jobid), category="harms", requestnumber="SYN-001", bcgovcode=code,
                       requestid="1", ministryrequestid="1", createdby="synthetic", attributes=json.dumps(attributes))
        mid = rdb.xadd(env["DIVISION_PDF_STITCH_STREAM_KEY"], message)
        return jobid, mid

    def consumed(mid):
        def has_been_consumed():
            sample()
            return rdb.get("$:lastid") == mid and not rdb.xrange(env["DIVISION_PDF_STITCH_STREAM_KEY"], min=mid, max=mid)

        wait_for(has_been_consumed, "cursor advance and input deletion")

    def publish(files, divisions=1):
        jobid, mid = enqueue(files, divisions)
        consumed(mid)
        return jobid, mid

    def document(name, labels):
        with fitz.open() as doc:
            for label in labels:
                doc.new_page().insert_text((60, 60), label)
            s3.put_object(Bucket=bucket, Key=name, Body=doc.tobytes())
        return dict(recordid=1, filename=name, s3uripath=f"https://{env['PDFSTITCH_S3_HOST']}/{bucket}/{name}", lastmodified="2026-01-01T00:00:00")

    ctx = dict(env=env, rdb=rdb, conn=conn, s3=s3, bucket=bucket, start=start, stop=stop,
               publish=publish, enqueue=enqueue, consumed=consumed, document=document, counter=counter,
               peak_kib=peak_kib, tmp_path=tmp_path)
    started = time.monotonic()
    try:
        yield ctx
    finally:
        sample()
        stop()
        print(json.dumps({"duration_seconds": round(time.monotonic() - started, 3), "worker_peak_rss_kib": peak_kib[0],
                          "sampled_peak_temporary_bytes": peak_tmp_bytes[0]}))
        rdb.delete(*[env[k] for k in ["DIVISION_PDF_STITCH_STREAM_KEY", "ZIPPER_STREAM_KEY", "NOTIFICATION_STREAM_KEY"]], "$:lastid")
        with conn.cursor() as cur:
            cur.execute('DELETE FROM public."PDFStitchJob" WHERE pdfstitchjobid BETWEEN %s AND %s', (int(token[:6], 16) * 10, counter[0]))
            cur.execute('DELETE FROM public."DocumentPathMapper" WHERE bucket=%s', (bucket,))
        conn.close()
        objects = s3.list_objects_v2(Bucket=bucket).get("Contents", [])
        for obj in objects:
            s3.delete_object(Bucket=bucket, Key=obj["Key"])
        s3.delete_bucket(Bucket=bucket)
        rdb.close()


@pytest.mark.parametrize("pages,divisions,missing", [(3, 2, False), (100, 1, False), (1, 1, True)])
def test_real_entrypoint_output_metadata_status_and_cursor(pipeline, pages, divisions, missing):
    p = pipeline
    labels = ["SYNTHETIC PAGE " + str(i) for i in range(pages)]
    files = [p["document"]("input.pdf", labels)]
    if missing:
        files.append(dict(files[0], filename="missing.pdf", s3uripath=files[0]["s3uripath"].replace("input.pdf", "missing.pdf")))
    # First start defaults to '$': leave an older entry behind, then prove
    # subsequent restarts neither replay it nor skip new work queued offline.
    _, historical_id = p["enqueue"](files)
    p["start"]()
    started = time.monotonic()
    jobid, mid = p["publish"](files, divisions)
    print(json.dumps({"pages": pages, "divisions": divisions, "missing_object": missing,
                      "processing_seconds": round(time.monotonic() - started, 3)}))
    events = p["rdb"].xrange(p["env"]["ZIPPER_STREAM_KEY"])
    assert len(events) == 1
    event = events[0][1]
    assert int(event[b"jobid"]) == jobid
    output = json.loads(event[b"finaloutput"])
    assert len(output["filestozip"]) == divisions
    assert len(output["stitchedoutput"]) == divisions
    for metadata in output["filestozip"]:
        prefix = f"https://{p['env']['PDFSTITCH_S3_HOST']}/{p['bucket']}/"
        assert metadata["s3uripath"].startswith(prefix)
        key = metadata["s3uripath"][len(prefix):]
        data = p["s3"].get_object(Bucket=p["bucket"], Key=key)["Body"].read()
        assert metadata["filename"].endswith(".pdf")
        with fitz.open(stream=data, filetype="pdf") as doc:
            assert len(doc) == pages
            assert [page.get_text().strip() for page in doc] == labels
    for division in output["stitchedoutput"]:
        assert division["skippedfiles"] == (["missing.pdf"] if missing else [])
    with p["conn"].cursor() as cur:
        cur.execute('SELECT status FROM public."PDFStitchJob" WHERE pdfstitchjobid=%s ORDER BY version', (jobid,))
        assert cur.fetchall() == [("started",)]  # Zipper, not this worker, completes successful jobs.
    assert p["rdb"].xlen(p["env"]["NOTIFICATION_STREAM_KEY"]) == 0
    assert p["rdb"].xrange(p["env"]["DIVISION_PDF_STITCH_STREAM_KEY"], min=historical_id, max=historical_id)
    # Resume with the literal cursor. Completed and unfinished jobs follow their current paths.
    p["stop"]()
    for state in ["completed", "started"]:
        nextid = p["counter"][0] + 1
        with p["conn"].cursor() as cur:
            cur.execute('INSERT INTO public."PDFStitchJob" (pdfstitchjobid,version,category,status) VALUES (%s,2,\'harms\',\'started\')', (nextid,))
            if state == "completed":
                cur.execute('INSERT INTO public."PDFStitchJob" (pdfstitchjobid,version,category,status) VALUES (%s,3,\'harms\',\'completed\')', (nextid,))
        p["start"]()
        p["publish"](files)
        p["stop"]()
    assert p["rdb"].xlen(p["env"]["ZIPPER_STREAM_KEY"]) == 1
    notifications = p["rdb"].xrange(p["env"]["NOTIFICATION_STREAM_KEY"])
    assert len(notifications) == 1 and notifications[0][1][b"errorflag"] == b"YES"
    # Publish while stopped. An implementation that ignores the saved cursor
    # and always starts at '$' will leave this job unprocessed.
    _, queued_id = p["enqueue"](files)
    p["start"]()
    p["consumed"](queued_id)
    assert p["rdb"].xlen(p["env"]["ZIPPER_STREAM_KEY"]) == 2
    assert p["rdb"].xrange(p["env"]["DIVISION_PDF_STITCH_STREAM_KEY"], min=historical_id, max=historical_id)
