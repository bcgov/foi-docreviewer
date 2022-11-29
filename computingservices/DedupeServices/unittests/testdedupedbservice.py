import unittest
from .testcontext import dedupedbservice
from models import dedupeproducermessage

#python -m unittest .\unittests\test_dedupedbservice.py
class TestDedupeDBService(unittest.TestCase):

    def test_dedupedbservice(self):                
        _message = dedupeproducermessage(s3filepath="edu-dev/TESTABIN/ABIN2399.pdf",bcgovcode="edu-dev-ut",requestnumber="EDU-UNIT-123",filename="unitest.pdf",ministryrequestid=100101)
        _hashcode ="1232-4562-6789"
        result = dedupedbservice.savedocumentdetails(_message,_hashcode)
        self.assertEqual(result,True)

    



if __name__ == '__main__':
    unittest.main()