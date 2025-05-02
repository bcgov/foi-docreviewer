import psycopg2
import boto3
from botocore.config import Config
from botocore.exceptions import NoCredentialsError
import os
from services.dbservices import get_daily_new_data, get_daily_data, get_all_data, get_table_list
from services.s3services import upload_to_s3
from utils.util import get_date_from_command_line
from dotenv import dotenv_values

is_local_test = True
if is_local_test:
    # Load environment variables from .env file for local testing
    env = dotenv_values(".env")

    # --- DB Configuration ---
    DATABASE_HOST = env.get("DATABASE_HOST")
    DATABASE_NAME = env.get("DATABASE_NAME")
    DATABASE_USER = env.get("DATABASE_USER")
    DATABASE_PASSWORD = env.get("DATABASE_PASSWORD")
    DATABASE_PORT = env.get("DATABASE_PORT")
    DOCREVIEWER_DATABASE_HOST = env.get("DOCREVIEWER_DATABASE_HOST")
    DOCREVIEWER_DATABASE_NAME = env.get("DOCREVIEWER_DATABASE_NAME")
    DOCREVIEWER_DATABASE_USER = env.get("DOCREVIEWER_DATABASE_USER")
    DOCREVIEWER_DATABASE_PASSWORD = env.get("DOCREVIEWER_DATABASE_PASSWORD")
    DOCREVIEWER_DATABASE_PORT = env.get("DOCREVIEWER_DATABASE_PORT")

    # --- S3 Configuration ---
    S3_HOST = env.get("S3_HOST")
    S3_REGION = env.get("S3_REGION")
    S3_ACCESS_KEY = env.get("S3_ACCESS_KEY")
    S3_SECRET_KEY = env.get("S3_SECRET_KEY")
    S3_BUCKET_NAME = env.get("S3_BUCKET_NAME")
    S3_ENV = env.get("S3_ENV")
else:
    # --- DB Configuration ---
    DATABASE_HOST = os.environ.get("DATABASE_HOST")
    DATABASE_NAME = os.environ.get("DATABASE_NAME")
    DATABASE_USER = os.environ.get("DATABASE_USER")
    DATABASE_PASSWORD = os.environ.get("DATABASE_PASSWORD")
    DATABASE_PORT = os.environ.get("DATABASE_PORT")
    DOCREVIEWER_DATABASE_HOST = os.environ.get("DOCREVIEWER_DATABASE_HOST")
    DOCREVIEWER_DATABASE_NAME = os.environ.get("DOCREVIEWER_DATABASE_NAME")
    DOCREVIEWER_DATABASE_USER = os.environ.get("DOCREVIEWER_DATABASE_USER")
    DOCREVIEWER_DATABASE_PASSWORD = os.environ.get("DOCREVIEWER_DATABASE_PASSWORD")
    DOCREVIEWER_DATABASE_PORT = os.environ.get("DOCREVIEWER_DATABASE_PORT")

    # --- S3 Configuration ---
    S3_HOST = os.environ.get("S3_HOST")
    S3_REGION = os.environ.get("S3_REGION")
    S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY")
    S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY")
    S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")
    S3_ENV = os.environ.get("S3_ENV")

def export_db(conn, db_name):
    """Main function to connect to PostgreSQL, fetch data, and upload to S3."""
    try:
        # Get the list of tables to process
        # This function should return a dictionary with keys 'table_with_created_completed_on', 'table_with_created_updated_at', 'table_with_created_at', 'table_with_createdat', and 'table_with_none'
        table_list = get_table_list(conn)
        # print(f"Tables to process: {table_list}")

        # Get the date from command line or use today's date
        given_date = get_date_from_command_line()
        print(f"Using date: {given_date}")

        # S3 client
        s3_client = boto3.client(
            "s3",
            config=Config(signature_version="s3"),
            endpoint_url=f"https://{S3_HOST}/",
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
            region_name=S3_REGION,
        )

        for table in table_list['table_with_created_completed_on']:
            print(f"Processing table: {table}")
            daily_data = get_daily_data(table, conn, "created_on", "completed_on", given_date)
            if daily_data:
                upload_to_s3(daily_data, table, s3_client, db_name, S3_BUCKET_NAME, S3_ENV ,given_date)
            else:
                print(f"No updates found for {table} after {given_date}.")

        for table in table_list['table_with_created_updated_at']:
            print(f"Processing table: {table}")
            daily_data = get_daily_data(table, conn, "created_at", "updated_at", given_date)
            if daily_data:
                upload_to_s3(daily_data, table, s3_client, db_name, S3_BUCKET_NAME, S3_ENV, given_date)
            else:
                print(f"No updates found for {table} after {given_date}.")

        for table in table_list['table_with_created_at']:
            print(f"Processing table: {table}")
            daily_data = get_daily_new_data(table, conn, "created_at", given_date)
            if daily_data:
                upload_to_s3(daily_data, table, s3_client, db_name, S3_BUCKET_NAME, S3_ENV, given_date)
            else:
                print(f"No updates found for {table} after {given_date}.")

        for table in table_list['table_with_createdat']:
            print(f"Processing table: {table}")
            daily_data = get_daily_new_data(table, conn, "createdat", given_date)
            if daily_data:
                upload_to_s3(daily_data, table, s3_client, db_name, S3_BUCKET_NAME, S3_ENV, given_date)
            else:
                print(f"No updates found for {table} after {given_date}.")

        for table in table_list['table_with_none']:
            print(f"Processing table: {table}")
            daily_data = get_all_data(table, conn)
            if daily_data:
                upload_to_s3(daily_data, table, s3_client, db_name, S3_BUCKET_NAME, S3_ENV, given_date)
            else:
                print(f"No updates found for {table} after {given_date}.")

    except psycopg2.Error as e:
        print(f"Error connecting to PostgreSQL: {e}")
    except NoCredentialsError:
        print("Error: AWS credentials not found.  Please configure credentials or provide access_key and secret_key.")
        return None
    except Exception as e:
        print(f"Error creating S3 client: {e}")
        return None
    finally:
        if conn:
            conn.close()
            print("PostgreSQL connection closed.")

def main():
    try:
        foi_db_conn = psycopg2.connect(
            host=DATABASE_HOST,
            database=DATABASE_NAME,
            user=DATABASE_USER,
            password=DATABASE_PASSWORD,
            port=DATABASE_PORT
        )
        print("Successfully connected to foi db.")
        export_db(foi_db_conn, DATABASE_NAME)

        docreviewer_db_conn = psycopg2.connect(
            host=DOCREVIEWER_DATABASE_HOST,
            database=DOCREVIEWER_DATABASE_NAME,
            user=DOCREVIEWER_DATABASE_USER,
            password=DOCREVIEWER_DATABASE_PASSWORD,
            port=DOCREVIEWER_DATABASE_PORT
        )
        print("Successfully connected to docreviewer db.")
        export_db(docreviewer_db_conn, DOCREVIEWER_DATABASE_NAME)

    except psycopg2.Error as e:
        print(f"Error connecting to PostgreSQL: {e}")


if __name__ == "__main__":
    main()