from . import foidedupehashcalulator
from .s3documentservice import getcredentialsbybcgovcode

def rundedupe(filepath):
    return foidedupehashcalulator.hash_file(filepath)


def processmessage(message):
    credentialattr = getcredentialsbybcgovcode(message.bcgovcode)
    print(credentialattr)