import os
import random
import redis
import time
from walrus import Database
import json
from dotenv import load_dotenv
load_dotenv()

STREAM_KEY = os.getenv('DOCUMENTSERVICE_STREAM_KEY')

redishost = os.getenv('DOCUMENTSERVICE_REDIS_HOST') 
redisport = os.getenv('DOCUMENTSERVICE_REDIS_PORT')
redispassword = os.getenv('DOCUMENTSERVICE_REDIS_PASSWORD')

db = Database(host=redishost, port=redisport, db=0,password=redispassword)
stream = db.Stream(STREAM_KEY)
encoder = json.JSONEncoder()
while True:

    jobs_dict = {'jobid': 51, 'category': 'harms', 'requestnumber': 'EDU-2023-04040757', 'bcgovcode': 'EDU', 'createdby': 'foiedu@idir', 'requestid': '518', 'ministryrequestid': '520', 'attributes': '[{"divisionname": "Learning and Education Programs", "divisionid": 3, "files": [{"s3uripath": "https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev-e/EDU-2023-28030430/5770c34d-c16e-4bbc-bcf5-837edab9a94c.png", "lastmodified": "2023-03-15T18:09:35.883Z", "recordid": 98, "filename": "download.png"},{"s3uripath": "https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev-e/EDU-2023-29030230/a512a03f-bdb0-439c-bb39-6cb868ef3887.jpg", "lastmodified": "2023-03-29T18:44:26.245Z", "recordid": 92, "filename": "blueprint.jpg"},{"s3uripath":"https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev-e/EDU-2023-03041156/b9efa6e2-d7fd-4bfd-9c9f-f549164f35e2.png","filename":"MicrosoftTeams-image.png", "lastmodified": "11/23/2022 23:26:21", "recordid": null}]}]'}
    
    job_id = stream.add(jobs_dict, id="*")
    print(f"Created job {job_id}:")
    
    time.sleep(random.randint(5, 10))
    