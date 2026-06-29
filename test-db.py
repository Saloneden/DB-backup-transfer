import os
from googleapiclient.discovery import build
from google.oauth2 import service_account
from dotenv import load_dotenv

load_dotenv()

PROJECT_ID = os.getenv('GCP_PROJECT_ID')
INSTANCE_ID = os.getenv('GCP_INSTANCE_ID')
KEY_PATH = os.getenv('GCP_KEY_PATH')

credentials = service_account.Credentials.from_service_account_file(KEY_PATH)
sql_admin = build('sqladmin', 'v1beta4', credentials=credentials)


def check_sql_instance_status():
    try:
        request = sql_admin.instances().get(project=PROJECT_ID, instance=INSTANCE_ID)
        response = request.execute()

        print("Cloud SQL instance details:")
        print(f"  id:       {response['name']}")
        print(f"  state:    {response['state']}")
        print(f"  version:  {response['databaseVersion']}")
        print(f"  ip:       {response.get('ipAddresses', 'no ip assigned')}")
        print(f"  region:   {response['region']}")

        if response['state'] == 'RUNNABLE':
            print(f"Instance '{INSTANCE_ID}' is up and running.")
        else:
            print(f"Instance '{INSTANCE_ID}' is in state: {response['state']}")

    except Exception as e:
        print(f"Error checking Cloud SQL instance status: {e}")


check_sql_instance_status()
