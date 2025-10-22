import logging
import os
import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    try:
        # Use DefaultAzureCredential which will automatically use the managed identity
        credential = DefaultAzureCredential()
        
        # Create BlobServiceClient using RBAC authentication
        account_name = os.environ['BLOB_ACCOUNT_NAME']
        blob_service_client = BlobServiceClient(
            account_url=f"https://{account_name}.blob.core.windows.net",
            credential=credential
        )
        
        # Access the blob
        container_name = os.environ['BLOB_CONTAINER']
        blob_name = os.environ['BLOB_NAME']
        
        blob_client = blob_service_client.get_blob_client(
            container=container_name,
            blob=blob_name
        )
        
        # Download blob content
        blob_data = blob_client.download_blob().readall()
        
        return func.HttpResponse(
            f"Successfully read blob using RBAC. Content: {blob_data.decode('utf-8')}",
            status_code=200
        )
        
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        return func.HttpResponse(
            f"Failed to read blob: {str(e)}",
            status_code=500
        )