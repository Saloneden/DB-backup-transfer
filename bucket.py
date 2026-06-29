import os
from google.cloud import storage
from google.oauth2 import service_account
from dotenv import load_dotenv

load_dotenv()

PROJECT_ID = os.getenv('GCP_PROJECT_ID')
KEY_PATH = os.getenv('GCP_KEY_PATH')
GCS_BUCKET_NAME = os.getenv('GCS_BUCKET_NAME')
GCS_BUCKET_LOCATION = os.getenv('GCS_BUCKET_LOCATION')

SQL_FILE_NAME = 'backup.sql'

credentials = service_account.Credentials.from_service_account_file(KEY_PATH)
storage_client = storage.Client(project=PROJECT_ID, credentials=credentials)


def create_bucket():
    try:
        bucket = storage_client.create_bucket(GCS_BUCKET_NAME, location=GCS_BUCKET_LOCATION)
        print(f"Bucket '{bucket.name}' created successfully in {GCS_BUCKET_LOCATION}.")

        # create an empty sql file and upload it as a placeholder
        with open(SQL_FILE_NAME, 'w') as sql_file:
            pass

        print(f"Empty SQL file '{SQL_FILE_NAME}' created.")

        blob = bucket.blob(SQL_FILE_NAME)
        blob.upload_from_filename(SQL_FILE_NAME)
        print(f"Uploaded '{SQL_FILE_NAME}' to gs://{GCS_BUCKET_NAME}/{SQL_FILE_NAME}.")

        # clean up the local copy
        os.remove(SQL_FILE_NAME)
        print(f"Local file '{SQL_FILE_NAME}' deleted.")

    except Exception as e:
        print(f"Error: {e}")


create_bucket()
