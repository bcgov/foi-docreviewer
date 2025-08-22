# import boto3
import json
import os
from datetime import date

S3_PREFIX = "daily_exports"  # Optional prefix for your S3 keys
def upload_to_s3(data, table_name, s3_client, db_name, bucket, env, given_date=None):
    """Uploads the data as a JSON file to S3."""
    # s3 = boto3.client("s3")
    if given_date is None:
        given_date = str(date.today())
    file_name = f"{S3_PREFIX}/{env}/{db_name}/{given_date}/{table_name}.json"
    json_data = json.dumps(data, default=str)  # Serialize datetime objects
    # print(f"JSON data: {json_data}")
    try:
        s3_client.put_object(Bucket=bucket, Key=file_name, Body=json_data)
        print(f"Successfully uploaded {file_name} to S3.")
    except Exception as e:
        print(f"Error uploading {file_name} to S3: {e}")