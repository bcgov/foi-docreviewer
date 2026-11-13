"""Opt-in packaged worker, private Redis/PostgreSQL and real signed HTTPS S3.

Use run-isolated.sh. SQL is a projection of the canonical DAL, not migrations.
No application imports: the only application process runs its shipped entrypoint.
"""
from io import BytesIO
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import uuid
import zipfile

import boto3
import psycopg2
import pytest
import redis
from PyPDF2 import PdfReader
from reportlab.pdfgen import canvas


def wait_for(check, description, timeout=45):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        time.sleep(0.05)
    pytest.fail("Timed out waiting for " + description)


@pytest.fixture
def pipeline(tmp_path):
    if os.getenv('RUN_ZIPPER_INTEGRATION') != '1':
        pytest.fail('Use integrationtests/run-isolated.sh with disposable infrastructure')
    env = os.environ.copy()
    assert env['DB_NAME'] == 'zipper_it_disposable'
    owner = env['ZIPPER_TEST_INSTANCE']
    assert owner.startswith('zipper-it-')
    rdb = redis.Redis(host=env['REDIS_HOST'], port=int(env['REDIS_PORT']), password=env['REDIS_PASSWORD'])
    assert rdb.get('zipper_it_owner') == owner.encode()
    assert rdb.dbsize() == 1, 'Refusing Redis with existing state'
    token = uuid.uuid4().hex
    env.update(ZIPPER_STREAM_KEY='zipper-it:' + token + ':input',
               NOTIFICATION_STREAM_KEY='zipper-it:' + token + ':notification', FAILUREATTEMPT='0')
    conn = psycopg2.connect(host=env['DB_HOST'], port=env['DB_PORT'], dbname=env['DB_NAME'],
                            user=env['DB_USER'], password=env['DB_PASSWORD'])
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute('SELECT token FROM zipper_it_owner')
        assert cur.fetchall() == [(owner,)], 'Refusing database not owned by this harness'
    s3 = boto3.client('s3', endpoint_url='https://' + env['S3_HOST'], region_name='us-east-1',
                      aws_access_key_id=env['AWS_ACCESS_KEY_ID'], aws_secret_access_key=env['AWS_SECRET_ACCESS_KEY'],
                      verify=env['REQUESTS_CA_BUNDLE'])
    code = 's' + token[:12]
    bucket = code + '-it-e'
    s3.create_bucket(Bucket=bucket)
    with conn.cursor() as cur:
        cur.execute('''CREATE TABLE IF NOT EXISTS public."PDFStitchJob" (
            pdfstitchjobid integer, version integer, ministryrequestid integer NOT NULL,
            category varchar(50) NOT NULL, inputfiles json NOT NULL, outputfiles json,
            status varchar(120) NOT NULL, message text, createdat timestamp NOT NULL DEFAULT now(),
            createdby varchar(120) NOT NULL, PRIMARY KEY(pdfstitchjobid,version));
            CREATE TABLE IF NOT EXISTS public."DocumentPathMapper" (bucket text, category text, attributes text);
            CREATE TABLE IF NOT EXISTS public."PDFStitchPackage" (
            pdfstitchpackageid serial, finalpackagepath varchar(500) NOT NULL,
            ministryrequestid integer NOT NULL, category varchar(50) NOT NULL,
            createdby varchar(120), createdat timestamp DEFAULT now(), PRIMARY KEY(pdfstitchpackageid,finalpackagepath));''')
        cur.execute('INSERT INTO public."DocumentPathMapper" VALUES (%s, %s, %s)',
                    (bucket, 'Records', json.dumps(dict(s3accesskey=env['AWS_ACCESS_KEY_ID'], s3secretkey=env['AWS_SECRET_ACCESS_KEY']))))
    workers = []
    peak = [0]

    def sample():
        for worker, log in workers:
            children = Path(f'/proc/{worker.pid}/task/{worker.pid}/children')
            for pid in [str(worker.pid)] + (children.read_text().split() if children.exists() else []):
                try:
                    for line in Path(f'/proc/{pid}/status').read_text().splitlines():
                        if line.startswith('VmHWM:'):
                            peak[0] = max(peak[0], int(line.split()[1]))
                except FileNotFoundError:
                    pass

    def start():
        log = tempfile.TemporaryFile()
        process = subprocess.Popen(['/bin/sh', './entrypoint.sh'], env=env, stdout=log, stderr=log, start_new_session=True)
        workers.append((process, log))

        def ready():
            sample()
            if process.poll() is not None:
                log.seek(0)
                pytest.fail('Worker exited: ' + log.read().decode()[-3000:])
            return any(client.get('cmd') == 'xread' for client in rdb.client_list())

        wait_for(ready, 'worker XREAD readiness')

    def stop():
        for process, log in workers:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=10)
            log.close()
        workers.clear()

    counter = [int(token[:6], 16) * 10]

    def enqueue(files, category='harms', folder=None, phase=None):
        counter[0] += 1
        jobid = counter[0]
        output = json.dumps({'stitchedoutput': [{'skippedfilecount': 1, 'skippedfiles': ['skipped.pdf']}]})
        message = dict(jobid=str(jobid), requestid='1', ministryrequestid=str(jobid), category=category,
                       requestnumber='SYN-' + str(jobid), bcgovcode=code, createdby='synthetic',
                       filestozip=json.dumps(files), finaloutput=output,
                       attributes='[]' if category == 'harms' else json.dumps('[]'), feeoverridereason='synthetic override')
        if folder is not None:
            message['foldername'] = folder
        if phase is not None:
            message['phase'] = phase
        return jobid, rdb.xadd(env['ZIPPER_STREAM_KEY'], message)

    def consumed(mid):
        def done():
            sample()
            return rdb.get('$:lastid') == mid and not rdb.xrange(env['ZIPPER_STREAM_KEY'], min=mid, max=mid)
        wait_for(done, 'cursor advance and input deletion')

    def document(name, body):
        s3.put_object(Bucket=bucket, Key=name, Body=body)
        return dict(filename=name, s3uripath=f"https://{env['S3_HOST']}/{bucket}/{name}")

    p = dict(env=env, rdb=rdb, conn=conn, s3=s3, bucket=bucket, start=start, stop=stop, enqueue=enqueue,
             consumed=consumed, document=document, peak=peak)
    started = time.monotonic()
    try:
        yield p
    finally:
        sample()
        # Logs remain available on a failed assertion, without printing environment/credentials.
        if os.getenv('ZIPPER_DEBUG_LOGS') == '1':
            for process, log in workers:
                log.seek(0)
                print(log.read().decode()[-6000:])
        stop()
        print(json.dumps(dict(duration_seconds=round(time.monotonic()-started, 3), worker_sampled_peak_rss_kib=peak[0],
                              container_memory_limit_mib=512)))
        # Only this fixture's keys, records and bucket in an owned disposable environment.
        rdb.delete(env['ZIPPER_STREAM_KEY'], env['NOTIFICATION_STREAM_KEY'], '$:lastid')
        with conn.cursor() as cur:
            cur.execute('DELETE FROM public."PDFStitchJob" WHERE pdfstitchjobid BETWEEN %s AND %s', (int(token[:6],16)*10,counter[0]))
            cur.execute('DELETE FROM public."PDFStitchPackage" WHERE ministryrequestid BETWEEN %s AND %s', (int(token[:6],16)*10,counter[0]))
            cur.execute('DELETE FROM public."DocumentPathMapper" WHERE bucket=%s', (bucket,))
        conn.close()
        for obj in s3.list_objects_v2(Bucket=bucket).get('Contents', []):
            s3.delete_object(Bucket=bucket, Key=obj['Key'])
        s3.delete_bucket(Bucket=bucket)
        rdb.close()


def package(p, jobid):
    with p['conn'].cursor() as cur:
        cur.execute('SELECT category, finalpackagepath FROM public."PDFStitchPackage" WHERE ministryrequestid=%s', (jobid,))
        return cur.fetchall()


def history(p, jobid):
    with p['conn'].cursor() as cur:
        cur.execute('SELECT version,category,status FROM public."PDFStitchJob" WHERE pdfstitchjobid=%s ORDER BY version', (jobid,))
        return cur.fetchall()


@pytest.mark.parametrize('category,phase,normalized,serviceid', [
    ('harms', None, 'harms', b'pdfstitchforharms'),
    ('redline', None, 'redline', b'pdfstitchforredline'),
    ('responsepackage', None, 'responsepackage', b'pdfstitchforresponsepackage'),
    ('redline_phase1', '1', 'redline', b'pdfstitchforredline'),
    ('responsepackage_phase2', '2', 'responsepackage', b'pdfstitchforresponsepackage'),
    ('openinfo', None, 'openinfo', None),
])
def test_archive_persistence_notifications_and_restart(pipeline, category, phase, normalized, serviceid):
    p = pipeline
    pdf = BytesIO()
    c = canvas.Canvas(pdf); c.setAuthor('Synthetic author')
    c.drawString(60,700,'SYNTHETIC SUMMARY'); c.showPage(); c.drawString(60,700,'SYNTHETIC PAGE TWO'); c.save()
    attachment = b'SYNTHETIC ATTACHMENT\x00\xff'
    files = [p['document']('summary.pdf', pdf.getvalue()), p['document']('nested/café attachment.bin', attachment)]
    _, historical = p['enqueue'](files)
    p['start']()
    started = time.monotonic()
    jobid, mid = p['enqueue'](files, category, 'Custom FOLDER', phase)
    p['consumed'](mid)
    assert history(p, jobid) == [(3, normalized+'-zipper', 'zippingstarted'), (4, normalized+'-zipper','zippingcompleted'), (5,normalized,'completed')]
    stored_category = category.replace('_','') if phase else category
    rows = package(p, jobid)
    assert len(rows) == 1
    assert rows[0][0] == stored_category
    key = f'SYN-{jobid}/Custom folder/SYN-{jobid}.zip'
    assert rows[0][1] == f"https://{p['env']['S3_HOST']}/{p['bucket']}/{key}"
    data = p['s3'].get_object(Bucket=p['bucket'], Key=key)['Body'].read()
    with zipfile.ZipFile(BytesIO(data)) as z:
        assert z.testzip() is None
        assert z.namelist() == ['summary.pdf','nested/café attachment.bin']
        assert z.read('nested/café attachment.bin') == attachment
        reader = PdfReader(BytesIO(z.read('summary.pdf')))
        assert [page.extract_text().strip() for page in reader.pages] == ['SYNTHETIC SUMMARY','SYNTHETIC PAGE TWO']
        assert reader.metadata.get('/Author') is None
    events = p['rdb'].xrange(p['env']['NOTIFICATION_STREAM_KEY'])
    assert len(events) == (1 if serviceid else 0)
    if serviceid:
        event = events[0][1]
        assert event[b'serviceid'] == serviceid
        assert event[b'errorflag'] == b'NO'
        if category == 'harms':
            assert event[b'totalskippedfilecount'] == b'1'
            assert json.loads(event[b'totalskippedfiles']) == ['skipped.pdf']
        if normalized == 'responsepackage':
            assert event[b'feeoverridereason'] == b'synthetic override'
    print(json.dumps(dict(category=category, archive_bytes=len(data), processing_seconds=round(time.monotonic()-started,3))))
    p['stop']()
    nextjob, queued = p['enqueue'](files, category, phase=phase)
    p['start'](); p['consumed'](queued)
    assert history(p,nextjob)[-1][2] == 'completed'
    assert p['rdb'].xrange(p['env']['ZIPPER_STREAM_KEY'], min=historical, max=historical)


@pytest.mark.parametrize('mode', ['missing-download', 'rejected-upload', 'connection-failure'])
def test_storage_failure_characterization_is_not_release_acceptance(pipeline, mode):
    p = pipeline
    files = [dict(filename='missing.pdf', s3uripath=f"https://{p['env']['S3_HOST']}/{p['bucket']}/missing.pdf")]
    if mode == 'rejected-upload':
        files = []
        with p['conn'].cursor() as cur:
            cur.execute('UPDATE public."DocumentPathMapper" SET attributes=%s WHERE bucket=%s',
                        (json.dumps(dict(s3accesskey='invalid',s3secretkey='invalid')),p['bucket']))
    elif mode == 'connection-failure':
        files[0]['s3uripath'] = 'https://127.0.0.1:1/missing.pdf'
    p['start']()
    jobid, mid = p['enqueue'](files)
    p['consumed'](mid)
    if mode == 'connection-failure':
        assert history(p,jobid) == [(3,'harms-zipper','zippingstarted'),(5,'harms','error')]
        assert package(p,jobid) == []
        events = p['rdb'].xrange(p['env']['NOTIFICATION_STREAM_KEY'])
        assert events[0][1][b'errorflag'] == b'YES'
    else:
        assert history(p,jobid)[-1] == (5,'harms','completed')  # Existing false success.
        rows = package(p,jobid); assert len(rows) == 1
        if mode == 'rejected-upload':
            assert not p['s3'].list_objects_v2(Bucket=p['bucket']).get('Contents')
        else:
            key = f'SYN-{jobid}/Harms/SYN-{jobid}.zip'
            data = p['s3'].get_object(Bucket=p['bucket'],Key=key)['Body'].read()
            with zipfile.ZipFile(BytesIO(data)) as z:
                assert z.testzip() is None
                assert b'NoSuchKey' in z.read('missing.pdf')  # HTTP error body archived as PDF.
        assert p['rdb'].xrange(p['env']['NOTIFICATION_STREAM_KEY'])[0][1][b'errorflag'] == b'NO'


@pytest.mark.parametrize('compressible', [True,False])
def test_bounded_large_archive_content_and_resources(pipeline, compressible):
    p = pipeline
    body = b'x' * (8*1024*1024) if compressible else os.urandom(8*1024*1024)
    files = [p['document']('large.bin',body)]
    p['start']()
    started = time.monotonic()
    jobid, mid = p['enqueue'](files); p['consumed'](mid)
    assert history(p,jobid)[-1][2] == 'completed'
    key = f'SYN-{jobid}/Harms/SYN-{jobid}.zip'
    data = p['s3'].get_object(Bucket=p['bucket'],Key=key)['Body'].read()
    with zipfile.ZipFile(BytesIO(data)) as z:
        assert z.testzip() is None
        assert z.read('large.bin') == body
    print(json.dumps(dict(compressible=compressible, input_bytes=len(body), archive_bytes=len(data), processing_seconds=round(time.monotonic()-started,3))))
