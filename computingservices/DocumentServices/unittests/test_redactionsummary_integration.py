import json
import os
import unittest

from dotenv import load_dotenv

load_dotenv()


class RedisPublisherIntegrationTests(unittest.TestCase):
    @unittest.skipUnless(
        all(
            os.getenv(name)
            for name in (
                "DOCUMENTSERVICE_STREAM_KEY",
                "DOCUMENTSERVICE_REDIS_HOST",
                "DOCUMENTSERVICE_REDIS_PORT",
            )
        ),
        "Redis integration env vars are not configured",
    )
    def test_can_publish_sample_message_to_stream(self):
        from walrus import Database

        stream_key = os.getenv("DOCUMENTSERVICE_STREAM_KEY")
        redishost = os.getenv("DOCUMENTSERVICE_REDIS_HOST")
        redisport = int(os.getenv("DOCUMENTSERVICE_REDIS_PORT"))
        redispassword = os.getenv("DOCUMENTSERVICE_REDIS_PASSWORD")

        db = Database(host=redishost, port=redisport, db=0, password=redispassword)
        stream = db.Stream(stream_key)

        jobs_dict = {
            "jobid": 51,
            "category": "harms",
            "requestnumber": "EDU-2023-04040757",
            "bcgovcode": "EDU",
            "createdby": "foiedu@idir",
            "requestid": "518",
            "ministryrequestid": "520",
            "attributes": json.dumps(
                [
                    {
                        "divisionname": "Learning and Education Programs",
                        "divisionid": 3,
                        "files": [
                            {
                                "s3uripath": "https://example/bucket/responsepackage/source.pdf",
                                "filename": "source.pdf",
                            }
                        ],
                    }
                ]
            ),
        }

        job_id = stream.add(jobs_dict, id="*")

        self.assertIsNotNone(job_id)


if __name__ == "__main__":
    unittest.main()
