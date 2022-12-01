import hashlib
from difflib import SequenceMatcher


def hash_file(filepath):

	# Use hashlib to store the hash of a file
	h1 = hashlib.sha1()	

	with open(filepath, "rb") as file:

		# Use file.read() to read the size of file
		# and read the file in small chunks
		# because we cannot read the large files.
		chunk = 0
		while chunk != b'':
			chunk = file.read(1024)
			h1.update(chunk)
			
		# hexdigest() is of 160 bits
		return h1.hexdigest()
