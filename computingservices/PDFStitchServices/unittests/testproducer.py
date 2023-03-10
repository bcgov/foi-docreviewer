import random
import redis
import time
from walrus import Database
import json

STREAM_KEY = "DIVISION-PDF-STITCH-local"

db = Database(host="localhost", port=6379, db=0,password=None)
stream = db.Stream(STREAM_KEY)
encoder = json.JSONEncoder()
while True:

    jobs_dict ={ 
        "requestnumber": "EDU-2023-03070" + str(random.randint(100, 500)),
        "attributes": encoder.encode([
            {
            "division":"div1",
            "files":[{"filename":"3eb0b1a5-0022-47ca-8e40-99e050f2c498.pdf","s3filepath":"https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev/EDU-2022-12345/3eb0b1a5-0022-47ca-8e40-99e050f2c498.pdf"},
                    {"filename":"1a832088-f7b0-4a03-bad3-a98ac3e5aacc.pdf","s3filepath":"https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev/EDU-2022-12345/1a832088-f7b0-4a03-bad3-a98ac3e5aacc.pdf"},
                    {"filename":"05d1c907-738b-4ab3-85b7-0170d0cd10f3.pdf","s3filepath":"https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev/EDU-2022-12345/05d1c907-738b-4ab3-85b7-0170d0cd10f3.pdf"}
                    ]
            },
            {"division":"div2",
            "files":[{"filename":"5700f73a-3e6b-4f90-9a89-ac79e70e2940.pdf","s3filepath":"https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev/EDU-2022-12345/5700f73a-3e6b-4f90-9a89-ac79e70e2940.pdf"}]
            }
        ])
    }
    
    print(jobs_dict)
    job_id = stream.add(jobs_dict, id="*")
    print(f"Created job {job_id}:")
    
    time.sleep(random.randint(5, 10))
    