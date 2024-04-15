import os
import random
import redis
import time
from walrus import Database
import json
from dotenv import load_dotenv
load_dotenv()

STREAM_KEY = os.getenv('ZIPPER_STREAM_KEY')

# redishost = os.getenv('REDIS_HOST') 
# redisport = os.getenv('REDIS_PORT')
# redispassword = os.getenv('REDIS_PASSWORD')

redishost = '142.34.194.68' 
redisport = 44602
redispassword = 'iWffXy381gEapMII'

db = Database(host=redishost, port=redisport, db=0,password=redispassword)
stream = db.Stream(STREAM_KEY)
encoder = json.JSONEncoder()
while True:
   
    jobs_dict = { 'jobid':  '1387',  'requestid':  '-1',  'category':  'redline',  'requestnumber':  'LDB-20240412-111',  'bcgovcode':  'ldb',  'createdby':  'suthirum@idir',  'ministryrequestid':  '2749',  'filestozip':  '[{"filename": "LDB-20240412-111-Redline.pdf", "s3uripath": "https://citz-foi-prod.objectstore.gov.bc.ca/ldb-test-e/LDB-20240412-111/redline/LDB-20240412-111-Redline.pdf"}, {"filename": "LDB-20240412-111-Redline- summary.pdf", "s3uripath": "https://citz-foi-prod.objectstore.gov.bc.ca/ldb-test-e/LDB-20240412-111/redline/LDB-20240412-111-Redline- summary.pdf"}]',  'finaloutput':  '',  'attributes':  '[{"divisionid": null, "divisionname": null, "includenrpages": false, "includeduplicatepages": false, "files": [{"filename": "LDB-20240412-111-Redline.pdf", "s3uripath": "https://citz-foi-prod.objectstore.gov.bc.ca/ldb-test-e/LDB-20240412-111/redline/LDB-20240412-111-Redline.pdf"}]}]',  'summarydocuments':  '{"pkgdocuments": [{"divisionid": 0, "documentids": [22152, 22154, 22153]}], "sorteddocuments": [22152, 22154, 22153]}',  'redactionlayerid':  '1'}
    
    job_id = stream.add(jobs_dict, id="*")
    print(f"Created job {job_id}:")
    
    time.sleep(random.randint(5, 10))
    