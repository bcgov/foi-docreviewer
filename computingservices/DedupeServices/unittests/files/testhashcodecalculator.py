import unittest
import hashcalculator

class Testhashcodecalculator(unittest.TestCase):

    def test_hascalc(self):
        testfilepath = 'C:\\AOT\\FOI\\Source\\foi-docreviewer\\foi-docreviewer\\computingservices\\DedupeServices\\unittests\\files\sample.pdf'
        documenthashvalue1 = hashcalculator.hash_file(testfilepath)
        self.assertIsNotNone(documenthashvalue1)
        documenthashvalue2 = hashcalculator.hash_file(testfilepath)
        self.assertEqual(documenthashvalue1,documenthashvalue2)



if __name__ == '__main__':
    unittest.main()