from services import dedupeservice
import sys

args = sys.argv[1:]
if __name__ == '__main__':
    print(args[0])
    filepath = args[0]
    hashvalue = dedupeservice.rundedupe(filepath)
    print(hashvalue)