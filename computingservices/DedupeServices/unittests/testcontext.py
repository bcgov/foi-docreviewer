import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from  utils import hashcalculator as hashcalc
from services import dedupedbservice as dedupedbservice , s3documentservice as s3documentservice

dedupeunittestbasedirectory =str.format('{0}\\unittests\\',os.getcwd()) 
