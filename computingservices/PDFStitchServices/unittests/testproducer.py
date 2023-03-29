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

    # jobs_dict = {'jobid': 45, 'category': 'harms', 'requestnumber': 'EDU-2023-28031103', 'bcgovcode': 'EDU', 'createdby': 'foiedu@idir', 'requestid': '9', 'ministryrequestid': '9', 'attributes': '[{"divisionname": "Deputy Ministers Office", "files": [{"s3uripath": "https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev-e/EDU-2023-28030430/5770c34d-c16e-4bbc-bcf5-837edab9a94c.png", "lastmodified": "2023-03-15T18:09:35.883Z", "recordid": 98, "filename": "download.png"},{"s3uripath": "https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev-e/EDU-2023-28031103/9cf915a5-e1aa-4668-a927-eb59b3ccd914.pdf", "lastmodified": "2023-03-09T21:10:29.084Z", "recordid": 94, "filename": "ram.xlsx.pdf"}, {"s3uripath": "https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev-e/EDU-2023-28031103/574c226a-a56d-438b-9a77-99e50bfed98a.pdf", "lastmodified": "2023-03-23T23:55:54.618Z", "recordid": 93, "filename": "ipsum.pdf"}, {"s3uripath": "https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev-e/EDU-2023-28031103/3dcc4486-5eb7-406d-8326-c841440d9e80.pdf", "lastmodified": "2023-03-24T01:21:51.965Z", "recordid": 92, "filename": "capbudg.xlsx.pdf"}], "divisionid": 2}]'}
    # jobs_dict = {'jobid': 45, 'category': 'harms', 'requestnumber': 'EDU-2023-28031103', 'bcgovcode': 'EDU', 'createdby': 'foiedu@idir', 'requestid': '9', 'ministryrequestid': '9', 'attributes': '[{"divisionname": "Deputy Ministers Office", "files": [{"s3uripath": "https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev-e/EDU-2023-28031103/574c226a-a56d-438b-9a77-99e50bfed98a.pdf", "lastmodified": "2023-03-23T23:55:54.618Z", "recordid": 93, "filename": "ipsum.pdf"},{"s3uripath": "https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev-e/EDU-2023-28031103/3dcc4486-5eb7-406d-8326-c841440d9e80.pdf", "lastmodified": "2023-03-24T01:21:51.965Z", "recordid": 92, "filename": "capbudg.xlsx.pdf"}], "divisionid": 2}]'}
    jobs_dict = {'jobid': 51, 'category': 'harms', 'requestnumber': 'EDU-2023-29030404', 'bcgovcode': 'EDU', 'createdby': 'foiedu@idir', 'requestid': '518', 'ministryrequestid': '520', 'attributes': '[{"divisionname": "Learning and Education Programs", "divisionid": 3, "files": [{"s3uripath": "https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev-e/EDU-2023-29030230/8e1822ea-2f5e-483d-985e-bf6bc80f77ee/doc-4.pdf", "lastmodified": "11/23/2022 23:26:21", "recordid": null, "filename": "doc-4.pdf"}, {"s3uripath": "https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev-e/EDU-2023-29030230/8e1822ea-2f5e-483d-985e-bf6bc80f77ee/potluck-23-mar-2022.pdf", "lastmodified": "11/23/2022 23:26:21", "recordid": null, "filename": "potluck-23-mar-2022.xlsx.pdf"}, {"s3uripath": "https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev-e/EDU-2023-29030230/e4488072-15ea-4ffe-bea4-d148ed911cc2.pdf", "lastmodified": "2022-12-28T19:05:10.900Z", "recordid": 96, "filename": "accessiBe_issues.xlsx.pdf"}, {"s3uripath": "https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev-e/EDU-2023-29030230/8e1822ea-2f5e-483d-985e-bf6bc80f77ee/Test MSG File with Attachments.pdf", "lastmodified": "02/08/2023 20:24:22", "recordid": null, "filename": "Test MSG File with Attachments.msg.pdf"}, {"s3uripath": "https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev-e/EDU-2023-29030230/e5b6d1af-55b1-48fe-b8c7-d210631f788d.pdf", "lastmodified": "2023-03-23T23:55:54.618Z", "recordid": 95, "filename": "ipsum.pdf"}, {"s3uripath": "https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev-e/EDU-2023-29030230/8e1822ea-2f5e-483d-985e-bf6bc80f77ee.pdf", "lastmodified": "2023-03-23T23:56:08.189Z", "recordid": 94, "filename": "testnested2.msg.pdf"}, {"s3uripath": "https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev-e/EDU-2023-29030230/3abd790e-7dc8-4ccb-9e08-8adedbdd40b8.pdf", "lastmodified": "2023-03-24T01:21:51.965Z", "recordid": 93, "filename": "capbudg.xlsx.pdf"}]}, {"divisionname": "Deputy Ministers Office", "divisionid": 2, "files": [{"s3uripath": "https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev-e/EDU-2023-29030230/6965db0f-26a7-4011-b72f-48deab1e8f4f.pdf", "lastmodified": "2022-11-10T16:42:05.893Z", "recordid": 91, "filename": "Fee Balance Outstanding Payment Receipt.pdf"}, {"s3uripath": "https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev-e/EDU-2023-29030230/64df3398-dc36-4023-85c4-4321490099c8.pdf", "lastmodified": "2022-11-21T23:26:06.800Z", "recordid": 90, "filename": "Tasks_to_be_tetsed.xlsx.pdf"}, {"s3uripath": "https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev-e/EDU-2023-29030230/dcd3c73e-bfcb-4731-a05f-8933186f20c4.pdf", "lastmodified": "2022-11-25T23:53:13.364Z", "recordid": 89, "filename": "InFLighttests.xlsx.pdf"}, {"s3uripath": "https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev-e/EDU-2023-29030230/87879217-d9e7-4c77-846a-210362f5c56d.txt", "lastmodified": "2022-12-01T00:00:34.826Z", "recordid": 88, "filename": "Deployment_Steps_Test.txt"}, {"s3uripath": "https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev-e/EDU-2023-29030230/2a259a59-c4e4-4ec5-9a20-278d101e3bcc.pdf", "lastmodified": "2022-12-09T20:48:18.073Z", "recordid": 87, "filename": "Deployment_Template.docx.pdf"}, {"s3uripath": "https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev-e/EDU-2023-29030230/a512a03f-bdb0-439c-bb39-6cb868ef3887.jpg", "lastmodified": "2023-03-29T18:44:26.245Z", "recordid": 92, "filename": "blueprint.jpg"}]}]'}
    
    job_id = stream.add(jobs_dict, id="*")
    print(f"Created job {job_id}:")
    
    time.sleep(random.randint(5, 10))
    