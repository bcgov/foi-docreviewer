Run script locally
a. create .env from .sampleenv and add values
b. edit foidbdailybackup.py, and set is_local_test to True
c. in a Python virtual environment, run the following in command line:

            pip install requirements.txt
            python foidbdailybackup.py 2025-05-01

            ##--- date parameter is optional, default value is current date.
            ##--- python script will export data updated after give date in foidb and docreviewer DB to JSON files in s3
d. check exported JSON files in s3: DataStagingBucket/daily_exports