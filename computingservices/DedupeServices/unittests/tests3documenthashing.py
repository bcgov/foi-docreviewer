import unittest
from .testcontext import s3documentservice
from models import dedupeproducermessage


#python -m unittest .\unittests\tests3documenthashing.py
class TestS3DocumentHashingService(unittest.TestCase):

    def test_dedupedbservice(self):                
        _message1 = dedupeproducermessage(s3filepath="edu-dev/TESTABIN/ABIN2399.pdf",bcgovcode="edu",requestnumber="EDU-UNIT-123",filename="unitest.pdf",ministryrequestid=100101)
        _message2 = dedupeproducermessage(s3filepath="edu-dev/TESTABIN/ABIN23.pdf",bcgovcode="edu",requestnumber="EDU-UNIT-123",filename="unitest.pdf",ministryrequestid=100101)
        _message3 = dedupeproducermessage(s3filepath="edu-dev/test-payment.pdf",bcgovcode="edu",requestnumber="EDU-UNIT-345",filename="test-payment.pdf",ministryrequestid=1001)
        result1 = s3documentservice.gets3documenthashcode(_message1)
        result2 = s3documentservice.gets3documenthashcode(_message2)
        result3 = s3documentservice.gets3documenthashcode(_message3)
        self.assertEqual(result1,result2)
        self.assertNotEqual(result1,result3)
