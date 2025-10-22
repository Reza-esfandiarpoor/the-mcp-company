import logging
import json
import os
import azure.functions as func
from azure.cosmos import CosmosClient
from datetime import datetime
import uuid

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('TestDbAccess function processed a request.')
    
    # Get Cosmos DB connection details from environment variables
    cosmos_endpoint = os.getenv('COSMOS_ENDPOINT')
    cosmos_key = os.getenv('COSMOS_KEY')
    database_name = os.getenv('COSMOS_DATABASE')
    container_name = os.getenv('COSMOS_CONTAINER')
    
    if not all([cosmos_endpoint, cosmos_key, database_name, container_name]):
        return func.HttpResponse(
            "Missing Cosmos DB configuration. Please check environment variables.",
            status_code=500
        )
    
    try:
        # Initialize Cosmos client
        client = CosmosClient(cosmos_endpoint, cosmos_key)
        database = client.get_database_client(database_name)
        container = database.get_container_client(container_name)
        
        # Create a test document
        test_id = str(uuid.uuid4())
        test_document = {
            'id': test_id,
            'message': 'Hello from Azure Function!',
            'timestamp': datetime.utcnow().isoformat(),
            'test_data': {
                'function_name': 'TestDbAccess',
                'test_type': 'write_read_test'
            }
        }
        
        # Write document to Cosmos DB
        logging.info(f'Writing document with id: {test_id}')
        created_item = container.create_item(body=test_document)
        logging.info('Document written successfully')
        
        # Read the document back
        logging.info(f'Reading document with id: {test_id}')
        read_item = container.read_item(item=test_id, partition_key=test_id)
        logging.info('Document read successfully')
        
        # Prepare response
        response_data = {
            'status': 'success',
            'operation': 'write_and_read',
            'document_id': test_id,
            'written_data': created_item,
            'read_data': read_item,
            'match': created_item == read_item
        }
        
        return func.HttpResponse(
            body=json.dumps(response_data, indent=2),
            mimetype="application/json",
            status_code=200
        )
        
    except Exception as e:
        error_response = {
            'status': 'error',
            'error_message': str(e),
            'error_type': type(e).__name__
        }
        logging.error(f'Error in TestDbAccess: {str(e)}')
        
        return func.HttpResponse(
            body=json.dumps(error_response, indent=2),
            mimetype="application/json",
            status_code=500
        )