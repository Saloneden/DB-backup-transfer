import os
from google.cloud import storage
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

GCS_BUCKET_NAME = os.getenv('GCS_BUCKET_NAME')
KEY_PATH = os.getenv('GCP_KEY_PATH')

file_size = 200 * 1024 * 1024  # 200 mb


def upload_large_file_to_gcs_resumable(bucket_name, file_size, key_path):
    today_date = datetime.now().strftime("%Y-%m-%d")
    file_name = f"random_file_{today_date}.bin"

    client = storage.Client.from_service_account_json(key_path)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(file_name)

    print(f"Uploading {file_size / (1024 * 1024):.0f} mb file to GCS...")

    # writes random bytes in 20 mb chunks using resumable upload
    chunk_size = 20 * 1024 * 1024
    with blob.open("wb", chunk_size=chunk_size) as f:
        remaining_size = file_size
        while remaining_size > 0:
            chunk = min(chunk_size, remaining_size)
            f.write(os.urandom(chunk))
            remaining_size -= chunk

    print(f"File '{file_name}' uploaded to bucket '{bucket_name}'.")


upload_large_file_to_gcs_resumable(GCS_BUCKET_NAME, file_size, KEY_PATH)
