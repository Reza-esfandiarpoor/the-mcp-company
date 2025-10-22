import logging
import traceback
import os

logging.info("Python function triggered to read blob.")

import azure.functions as func
from azure.storage.blob import BlobServiceClient

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Python function triggered to read blob.")

    account_name = os.getenv("BLOB_ACCOUNT_NAME")
    account_key  = os.getenv("BLOB_ACCOUNT_KEY")
    container    = os.getenv("BLOB_CONTAINER")
    blob_name    = os.getenv("BLOB_NAME")
    try:
        conn_str = (
            f"DefaultEndpointsProtocol=https;"
            f"AccountName={account_name};"
            f"AccountKey={account_key};"
            f"EndpointSuffix=core.windows.net"
        )
        blob_service_client = BlobServiceClient.from_connection_string(conn_str)
        blob_client = blob_service_client.get_blob_client(container=container, blob=blob_name)
        data = blob_client.download_blob().readall()
        return func.HttpResponse(f"Blob contents:\n{data.decode('utf-8')}", status_code=200)
    except Exception as e:
        logging.error(traceback.format_exc()) 
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)

