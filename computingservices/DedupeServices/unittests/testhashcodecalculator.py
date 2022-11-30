import unittest
import os
from .testcontext import hashcalc , dedupeunittestbasedirectory

#python -m unittest .\unittests\testhashcodecalculator.py
class Testhashcodecalculator(unittest.TestCase):

    def test_hascalc(self):                
        testfilepath = str.format('{0}\\files\\sample.pdf', dedupeunittestbasedirectory)
        documenthashvalue1 = hashcalc.hash_file(testfilepath)
        self.assertIsNotNone(documenthashvalue1)
        documenthashvalue2 = hashcalc.hash_file(testfilepath)       
        self.assertEqual(documenthashvalue1,documenthashvalue2)



if __name__ == '__main__':
    unittest.main()