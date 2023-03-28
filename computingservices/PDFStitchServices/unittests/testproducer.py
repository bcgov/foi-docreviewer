import os
import random
import redis
import time
from walrus import Database
import json
from dotenv import load_dotenv
load_dotenv()

STREAM_KEY = os.getenv('DIVISION_PDF_STITCH_STREAM_KEY')

redishost = os.getenv('PDFSTITCH_REDIS_HOST') 
redisport = os.getenv('PDFSTITCH_REDIS_PORT')
redispassword = os.getenv('PDFSTITCH_REDIS_PASSWORD')

db = Database(host=redishost, port=redisport, db=0,password=redispassword)
stream = db.Stream(STREAM_KEY)
encoder = json.JSONEncoder()
while True:

    # jobs_dict ={ 
    #     "requestnumber": "EDU-2023-03070" + str(random.randint(100, 500)),
    #     "bcgovcode": "edu",
    #     "attributes": encoder.encode([
    #         {
    #         "division":"div1",
    #         "files":[{"filename":"3eb0b1a5-0022-47ca-8e40-99e050f2c498.pdf","s3filepath":"https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev/EDU-2022-12345/3eb0b1a5-0022-47ca-8e40-99e050f2c498.pdf"},
    #                 {"filename":"1a832088-f7b0-4a03-bad3-a98ac3e5aacc.pdf","s3filepath":"https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev/EDU-2022-12345/1a832088-f7b0-4a03-bad3-a98ac3e5aacc.pdf"},
    #                 {"filename":"download.png","s3filepath":"https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev-e/EDU-2022-12345/download.png"},
    #                 {"filename":"05d1c907-738b-4ab3-85b7-0170d0cd10f3.pdf","s3filepath":"https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev/EDU-2022-12345/05d1c907-738b-4ab3-85b7-0170d0cd10f3.pdf"},
    #                 {"filename":"MicrosoftTeams-image.png","s3filepath":"https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev-e/EDU-2022-12345/MicrosoftTeams-image.png"},
    #                 ]
    #         },
    #         {"division":"div2",
    #         "files":[{"filename":"5700f73a-3e6b-4f90-9a89-ac79e70e2940.pdf","s3filepath":"https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev/EDU-2022-12345/5700f73a-3e6b-4f90-9a89-ac79e70e2940.pdf"}]
    #         },
    #         {"division":"div3",
    #         "files":[{"filename":"download.png","s3filepath":"https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev-e/EDU-2022-12345/download.png"}]
    #         }
    #     ])
    # }

    jobs_dict = {'jobid': 45, 'category': 'harms', 'requestnumber': 'EDU-2023-28031103', 'bcgovcode': 'EDU', 'createdby': 'foiedu@idir', 'requestid': '9', 'ministryrequestid': '9', 'attributes': '[{"divisionname": "Deputy Ministers Office", "files": [{"s3uripath": "https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev-e/EDU-2023-28031103/9cf915a5-e1aa-4668-a927-eb59b3ccd914.pdf", "lastmodified": "2023-03-09T21:10:29.084Z", "recordid": 94, "filename": "ram.xlsx.pdf"}, {"s3uripath": "https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev-e/EDU-2023-28031103/574c226a-a56d-438b-9a77-99e50bfed98a.pdf", "lastmodified": "2023-03-23T23:55:54.618Z", "recordid": 93, "filename": "ipsum.pdf"}, {"s3uripath": "https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev-e/EDU-2023-28031103/3dcc4486-5eb7-406d-8326-c841440d9e80.pdf", "lastmodified": "2023-03-24T01:21:51.965Z", "recordid": 92, "filename": "capbudg.xlsx.pdf"}], "divisionid": 2}]'}
    # jobs_dict = {'jobid': 45, 'category': 'harms', 'requestnumber': 'EDU-2023-28031103', 'bcgovcode': 'EDU', 'createdby': 'foiedu@idir', 'requestid': '9', 'ministryrequestid': '9', 'attributes': '[{"divisionname": "Deputy Ministers Office", "files": [{"s3uripath": "https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev-e/EDU-2023-28031103/574c226a-a56d-438b-9a77-99e50bfed98a.pdf", "lastmodified": "2023-03-23T23:55:54.618Z", "recordid": 93, "filename": "ipsum.pdf"},{"s3uripath": "https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev-e/EDU-2023-28031103/3dcc4486-5eb7-406d-8326-c841440d9e80.pdf", "lastmodified": "2023-03-24T01:21:51.965Z", "recordid": 92, "filename": "capbudg.xlsx.pdf"}], "divisionid": 2}]'}
    
    
    job_id = stream.add(jobs_dict, id="*")
    print(f"Created job {job_id}:")
    
    time.sleep(random.randint(5, 10))
    