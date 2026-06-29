import boto3
import os
from google.cloud import storage
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from botocore.exceptions import NoCredentialsError
from tqdm import tqdm
from datetime import datetime
import time
import requests
from dotenv import load_dotenv

load_dotenv()

PROJECT_ID = os.getenv('GCP_PROJECT_ID')
INSTANCE_ID = os.getenv('GCP_INSTANCE_ID')
DATABASE_NAME = os.getenv('GCP_DATABASE_NAME')
KEY_PATH = os.getenv('GCP_KEY_PATH')
GCS_BUCKET_NAME = os.getenv('GCS_BUCKET_NAME')
EXPORT_PATH_PREFIX = os.getenv('EXPORT_PATH_PREFIX')
AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY')
AWS_SECRET_KEY = os.getenv('AWS_SECRET_KEY')
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
S3_REGION = os.getenv('S3_REGION')
SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL')

credentials = service_account.Credentials.from_service_account_file(KEY_PATH)
sql_admin = build('sqladmin', 'v1beta4', credentials=credentials)
storage_client = storage.Client.from_service_account_json(KEY_PATH)
s3_client = boto3.client('s3', aws_access_key_id=AWS_ACCESS_KEY, aws_secret_access_key=AWS_SECRET_KEY, region_name=S3_REGION)


def send_slack_notification(message):
    try:
        response = requests.post(
            SLACK_WEBHOOK_URL,
            json={"text": message},
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 200:
            print("Slack notification sent successfully.")
        else:
            print(f"Failed to send Slack notification. Status code: {response.status_code}")
    except Exception as e:
        print(f"Error sending Slack notification: {e}")


def export_cloud_sql_to_bucket():
    try:
        today_date = datetime.now().strftime('%Y-%m-%d')
        export_file_name = f"{EXPORT_PATH_PREFIX}_{today_date}.sql.gz"

        export_config = {
            'exportContext': {
                'fileType': 'SQL',
                'uri': f'gs://{GCS_BUCKET_NAME}/{export_file_name}',
                'databases': [DATABASE_NAME],
                'compression': 'GZIP',
            }
        }

        request = sql_admin.instances().export(project=PROJECT_ID, instance=INSTANCE_ID, body=export_config)
        response = request.execute()

        print(f"Export started: {response}")

        operation_name = response.get('name')
        if operation_name:
            check_export_status(operation_name)
            transfer_to_s3(today_date)
            delete_old_exports(today_date)

    except HttpError as err:
        print(f"Error exporting database: {err}")
        send_slack_notification(f"Error exporting database: {err}")
    except Exception as e:
        print(f"Unexpected error: {e}")
        send_slack_notification(f"Unexpected error: {e}")


def check_export_status(operation_name):
    try:
        # polls every 5 seconds until the export is done
        while True:
            request = sql_admin.operations().get(project=PROJECT_ID, operation=operation_name)
            response = request.execute()

            status = response.get('status')
            if status == 'DONE':
                print("Export operation completed successfully.")
                break
            else:
                print("Export operation is still in progress...")
                time.sleep(5)

    except HttpError as err:
        print(f"Error checking export status: {err}")
        send_slack_notification(f"Error checking export status: {err}")
    except Exception as e:
        print(f"Unexpected error checking export status: {e}")
        send_slack_notification(f"Unexpected error checking export status: {e}")


def delete_old_exports(today_date):
    # removes anything in the bucket that isnt todays backup
    try:
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blobs = list(bucket.list_blobs())

        for blob in blobs:
            if not blob.name.endswith(f"{today_date}.sql.gz"):
                print(f"Deleting old or unrelated file: {blob.name}")
                blob.delete()

        print("Old or unrelated files deleted successfully.")

    except Exception as e:
        print(f"Error deleting old or unrelated files: {e}")
        send_slack_notification(f"Error deleting old or unrelated files: {e}")


def find_file_in_gcs(bucket_name, date_prefix):
    # looks for todays export file in the bucket
    try:
        bucket = storage_client.bucket(bucket_name)
        blobs = bucket.list_blobs()

        for blob in blobs:
            if date_prefix in blob.name:
                return blob.name
        return None
    except Exception as e:
        print(f"Error finding file in GCS: {e}")
        send_slack_notification(f"Error finding file in GCS: {e}")


def upload_large_file_gcs_to_s3(gcs_bucket, gcs_filename, s3_bucket, s3_filename, part_size_mb=50):
    try:
        bucket = storage_client.bucket(gcs_bucket)
        blob = bucket.blob(gcs_filename)

        blob.reload()
        file_size = blob.size
        if file_size is None:
            print("Failed to retrieve file size from GCS.")
            return False

        print(f"Starting transfer from GCS to S3 ({file_size} bytes)...")

        # streams the file in chunks directly to s3 without saving it locally
        multipart_upload = s3_client.create_multipart_upload(Bucket=s3_bucket, Key=s3_filename)
        part_size = part_size_mb * 1024 * 1024
        parts = []
        part_number = 1

        with tqdm(total=file_size, unit='B', unit_scale=True, desc="Transferring") as pbar:
            download_stream = blob.open("rb")
            while chunk := download_stream.read(part_size):
                response = s3_client.upload_part(
                    Bucket=s3_bucket,
                    Key=s3_filename,
                    PartNumber=part_number,
                    UploadId=multipart_upload['UploadId'],
                    Body=chunk,
                )
                parts.append({"PartNumber": part_number, "ETag": response["ETag"]})
                part_number += 1
                pbar.update(len(chunk))

        s3_client.complete_multipart_upload(
            Bucket=s3_bucket,
            Key=s3_filename,
            UploadId=multipart_upload['UploadId'],
            MultipartUpload={"Parts": parts},
        )

        print(f"File successfully transferred from GCS to S3 as {s3_filename}")

        # remove from gcs after a successful transfer
        blob.delete()
        print(f"Deleted file from GCS: {gcs_filename}")

        return True

    except FileNotFoundError:
        print("The file was not found.")
        send_slack_notification("The file was not found in GCS.")
    except NoCredentialsError:
        print("AWS credentials are not available.")
        send_slack_notification("AWS credentials are missing or invalid.")
    except Exception as e:
        print(f"An error occurred: {e}")
        send_slack_notification(f"An error occurred during the transfer: {e}")
    return False


def transfer_to_s3(today_date):
    try:
        gcs_file_name = find_file_in_gcs(GCS_BUCKET_NAME, today_date)
        if not gcs_file_name:
            print(f"No file found in GCS with today's date: {today_date}")
            send_slack_notification(f"No file found in GCS with today's date: {today_date}")
        else:
            s3_file_name = f"backup-{today_date}.sql"
            if upload_large_file_gcs_to_s3(GCS_BUCKET_NAME, gcs_file_name, S3_BUCKET_NAME, s3_file_name):
                print(f"Backup successfully uploaded to S3: {s3_file_name}")
                send_slack_notification(f"Backup successfully transferred to S3: {s3_file_name}")

    except Exception as e:
        print(f"Error during transfer to S3: {e}")
        send_slack_notification(f"Error during transfer to S3: {e}")


export_cloud_sql_to_bucket()
