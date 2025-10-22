import datetime
from typing import Dict

import requests
from azure.identity import EnvironmentCredential

api_version = "2021-04-01"
cred = EnvironmentCredential()


def get_x_ms_date() -> str:
    return datetime.datetime.now(datetime.UTC).strftime("%a, %d %b %Y %H:%M:%S GMT")


def list_resources(subscription_id: str):
    token = cred.get_token("https://management.azure.com/.default")
    # REST API endpoint to list all resources in the subscription
    url = f"https://management.azure.com/subscriptions/{subscription_id}/resources?api-version={api_version}"

    headers = {
        "Authorization": f"Bearer {token.token}",
        "Content-Type": "application/json",
    }

    # Make the REST call
    response = requests.get(url, headers=headers)

    # Handle response
    if response.status_code == 200:
        return response.json()["value"]
    else:
        print(f"Error: {response.status_code} - {response.text}")


def list_resources_in_rg(subscription_id: str, resource_group: str):
    token = cred.get_token("https://management.azure.com/.default")
    # REST API endpoint to list all resources in the subscription
    url = f"https://management.azure.com/subscriptions/{subscription_id}/resourceGroups/{resource_group}/resources?api-version={api_version}"

    headers = {
        "Authorization": f"Bearer {token.token}",
        "Content-Type": "application/json",
    }

    # Make the REST call
    response = requests.get(url, headers=headers)

    # Handle response
    if response.status_code == 200:
        return response.json()["value"]
    else:
        print(f"Error: {response.status_code} - {response.text}")


def list_kv_secrets(vault_name: str):
    token = cred.get_token("https://vault.azure.net/.default").token
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://{vault_name}.vault.azure.net/secrets?api-version=7.4"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json().get("value", [])


def read_text_from_blob(storage_acct: str, container: str, blobname: str):

    token = cred.get_token("https://storage.azure.com/.default").token
    # Blob URL
    blob_url = f"https://{storage_acct}.blob.core.windows.net/{container}/{blobname}"

    # Upload the text using REST API
    headers = {
        "Authorization": f"Bearer {token}",
        "x-ms-version": "2021-08-06",
    }

    response = requests.get(blob_url, headers=headers)
    response.raise_for_status()
    return response.content.decode("utf-8")


def blob_exists(storage_account: str, container: str, blob: str) -> bool:
    # Get OAuth2 token for storage
    token = cred.get_token("https://storage.azure.com/.default").token

    url = f"https://{storage_account}.blob.core.windows.net/{container}/{blob}"
    headers = {
        "Authorization": f"Bearer {token}",
        "x-ms-version": "2021-12-02",
    }

    resp = requests.head(url, headers=headers)

    if resp.status_code == 200:
        return True
    elif resp.status_code == 404:
        return False
    else:
        # Something else went wrong (permissions, wrong container, etc.)
        print("Error:", resp.status_code, resp.text)
        resp.raise_for_status()


def backup_secret(vault_name: str, secret_name: str):
    token = cred.get_token("https://vault.azure.net/.default").token
    headers = {"Authorization": f"Bearer {token}"}
    backup_url = f"https://{vault_name}.vault.azure.net/secrets/{secret_name}/backup?api-version=7.4"
    resp = requests.post(backup_url, headers=headers)
    resp.raise_for_status()
    return resp.json()["value"]


def langdetect_txt(
    subscription_id: str, resource_group: str, acct: str, endpoint: str, detect_me: str
):
    token = cred.get_token("https://cognitiveservices.azure.com/.default").token

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Ocp-Apim-Subscription-Region": "eastus",
        # anthaue TODO: construct this by passing the sub id and res id in here.
        "Ocp-Apim-ResourceId": f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.CognitiveServices/accounts/{acct}",
    }

    url = endpoint + f"/detect?api-version=3.0"

    # Text to detect
    body = [{"Text": detect_me}]
    response = requests.post(url, headers=headers, json=body)
    response.raise_for_status()
    result = response.json()
    return result[0]["language"]


def get_static_website_url_arm(
    subscription_id: str, resource_group: str, storage_account: str
):
    token = cred.get_token("https://management.azure.com/.default").token

    url = f"https://management.azure.com/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Storage/storageAccounts/{storage_account}?api-version=2023-01-01"

    headers = {"Authorization": f"Bearer {token}"}

    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    data = resp.json()

    web_endpoint = data.get("properties", {}).get("primaryEndpoints", {}).get("web")
    print("Static website URL:", web_endpoint)
    return web_endpoint


def add_row_to_table(account_name: str, table_name: str, row_data: Dict):

    token = cred.get_token("https://storage.azure.com/.default").token
    url = f"https://{account_name}.table.core.windows.net/{table_name}"
    request_time = get_x_ms_date()

    headers = {
        "x-ms-date": request_time,
        "x-ms-version": "2019-02-02",
        "Authorization": f"Bearer {token}",
        "Accept": "application/json;odata=nometadata",
        "Content-Type": "application/json",
    }

    resp = requests.post(url, headers=headers, json=row_data)

    if resp.status_code in (201, 204):
        print("Entity inserted successfully")
    else:
        print("Failed:", resp.status_code, resp.text)


def get_table_entities(account_name: str, table_name: str):

    url = f"https://{account_name}.table.core.windows.net/{table_name}"
    token = cred.get_token("https://storage.azure.com/.default").token

    headers = {
        "Authorization": f"Bearer {token}",
        "x-ms-date": get_x_ms_date(),
        "x-ms-version": "2019-02-02",
        "Accept": "application/json;odata=nometadata",
    }

    # Example: select all entities
    resp = requests.get(url, headers=headers)
    resp.raise_for_status() 
    return resp.json()["value"]

# specification/storage/resource-manager/Microsoft.Storage/stable/2019-06-01/storage.yaml
# StorageAccounts_Update
def disable_storage_account_key_auth(
    subscription_id: str, resource_group: str, storage_account: str
):
    """Disable key-based authentication for a storage account"""
    token = cred.get_token("https://management.azure.com/.default")
    
    # REST API endpoint to update storage account properties
    url = f"https://management.azure.com/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Storage/storageAccounts/{storage_account}?api-version=2023-01-01"
    
    headers = {
        "Authorization": f"Bearer {token.token}",
        "Content-Type": "application/json",
    }
    
    # Request body to disable shared key access
    body = {
        "properties": {
            "allowSharedKeyAccess": False
        }
    }
    
    # Make the PATCH request to update the storage account
    response = requests.patch(url, headers=headers, json=body)
    
    # Handle response
    if response.status_code == 200:
        print(f"Successfully disabled key-based auth for storage account: {storage_account}")
        return response.json()
    else:
        print(f"Error: {response.status_code} - {response.text}")
        response.raise_for_status()

# specification/storage/resource-manager/Microsoft.Storage/stable/2019-06-01/storage.yaml
# StorageAccounts_Update
def enable_storage_account_key_auth(
    subscription_id: str, resource_group: str, storage_account: str
):
    """Enable key-based authentication for a storage account"""
    token = cred.get_token("https://management.azure.com/.default")
    
    # REST API endpoint to update storage account properties
    url = f"https://management.azure.com/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Storage/storageAccounts/{storage_account}?api-version=2023-01-01"
    
    headers = {
        "Authorization": f"Bearer {token.token}",
        "Content-Type": "application/json",
    }
    
    # Request body to enable shared key access
    body = {
        "properties": {
            "allowSharedKeyAccess": True
        }
    }
    
    # Make the PATCH request to update the storage account
    response = requests.patch(url, headers=headers, json=body)
    
    # Handle response
    if response.status_code == 200:
        print(f"Successfully enabled key-based auth for storage account: {storage_account}")
        return response.json()
    else:
        print(f"Error: {response.status_code} - {response.text}")
        response.raise_for_status()

# specification/web/resource-manager/Microsoft.Web/stable/2024-04-01/WebApps.yaml
# WebApps_ListPublishingCredentials
def read_function_file(
    subscription_id: str, resource_group: str, function_app_name: str, file_path: str
):
    """Read a specific file from function app using Kudu VFS API"""
    token = cred.get_token("https://management.azure.com/.default")
    
    # Get publishing credentials
    creds_url = f"https://management.azure.com/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Web/sites/{function_app_name}/config/publishingcredentials/list?api-version=2022-03-01"
    
    headers = {
        "Authorization": f"Bearer {token.token}",
        "Content-Type": "application/json",
    }
    
    creds_response = requests.post(creds_url, headers=headers)
    creds_response.raise_for_status()
    creds = creds_response.json()
    
    # Read file via Kudu VFS
    vfs_url = f"https://{function_app_name}.scm.azurewebsites.net/api/vfs/site/wwwroot/{file_path}"
    auth = (creds["properties"]["publishingUserName"], creds["properties"]["publishingPassword"])
    
    file_response = requests.get(vfs_url, auth=auth)
    file_response.raise_for_status()
    
    return file_response.text


# specification/web/resource-manager/Microsoft.Web/stable/2024-04-01/WebApps.yaml
# WebApps_ListPublishingCredentials
def write_function_file(
    subscription_id: str, resource_group: str, function_app_name: str, 
    file_path: str, content: str
):
    """Write/update a specific file in function app using Kudu VFS API"""
    token = cred.get_token("https://management.azure.com/.default")
    
    # Get publishing credentials
    creds_url = f"https://management.azure.com/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Web/sites/{function_app_name}/config/publishingcredentials/list?api-version=2022-03-01"
    
    headers = {
        "Authorization": f"Bearer {token.token}",
        "Content-Type": "application/json",
    }
    
    creds_response = requests.post(creds_url, headers=headers)
    creds_response.raise_for_status()
    creds = creds_response.json()
    
    # Write file via Kudu VFS
    vfs_url = f"https://{function_app_name}.scm.azurewebsites.net/api/vfs/site/wwwroot/{file_path}"
    auth = (creds["properties"]["publishingUserName"], creds["properties"]["publishingPassword"])
    
    vfs_headers = {
        "Content-Type": "text/plain",
        "If-Match": "*"  # Overwrite if exists
    }
    
    write_response = requests.put(vfs_url, auth=auth, headers=vfs_headers, data=content)
    write_response.raise_for_status()
    
    print(f"Successfully updated {file_path}")

# specification/web/resource-manager/Microsoft.Web/stable/2024-04-01/WebApps.yaml
# WebApps_Restart
def restart_function_app(
    subscription_id: str, resource_group: str, function_app_name: str
):
    """Restart a function app to ensure changes are picked up"""
    token = cred.get_token("https://management.azure.com/.default")
    
    url = f"https://management.azure.com/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Web/sites/{function_app_name}/restart?api-version=2022-03-01"
    
    headers = {
        "Authorization": f"Bearer {token.token}",
        "Content-Type": "application/json",
    }
    
    response = requests.post(url, headers=headers)
    
    if response.status_code in [200, 202, 204]:
        print(f"Successfully restarted function app: {function_app_name}")
        return True
    else:
        print(f"Error: {response.status_code} - {response.text}")
        response.raise_for_status()

# specification/web/resource-manager/Microsoft.Web/stable/2024-04-01/WebApps.yaml
# WebApps_Stop
def stop_function_app(
    subscription_id: str, resource_group: str, function_app_name: str
):
    """Stop a function app"""
    token = cred.get_token("https://management.azure.com/.default")
    
    url = f"https://management.azure.com/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Web/sites/{function_app_name}/stop?api-version=2022-03-01"
    
    headers = {
        "Authorization": f"Bearer {token.token}",
        "Content-Type": "application/json",
    }
    
    response = requests.post(url, headers=headers)
    
    if response.status_code in [200, 202, 204]:
        print(f"Successfully stopped function app: {function_app_name}")
        return True
    else:
        print(f"Error: {response.status_code} - {response.text}")
        response.raise_for_status()


# specification/web/resource-manager/Microsoft.Web/stable/2024-04-01/WebApps.yaml
# WebApps_Start
def start_function_app(
    subscription_id: str, resource_group: str, function_app_name: str
):
    """Start a function app"""
    token = cred.get_token("https://management.azure.com/.default")
    
    url = f"https://management.azure.com/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Web/sites/{function_app_name}/start?api-version=2022-03-01"
    
    headers = {
        "Authorization": f"Bearer {token.token}",
        "Content-Type": "application/json",
    }
    
    response = requests.post(url, headers=headers)
    
    if response.status_code in [200, 202, 204]:
        print(f"Successfully started function app: {function_app_name}")
        return True
    else:
        print(f"Error: {response.status_code} - {response.text}")
        response.raise_for_status()

# StorageAccounts_GetProperties
# specification/storage/resource-manager/Microsoft.Storage/stable/2019-06-01/storage.yaml
def get_storage_account_properties(
    subscription_id: str, resource_group: str, storage_account: str
):
    """Get properties of a storage account including allowSharedKeyAccess"""
    token = cred.get_token("https://management.azure.com/.default")
    
    # REST API endpoint to get storage account properties
    url = f"https://management.azure.com/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Storage/storageAccounts/{storage_account}?api-version=2023-01-01"
    
    headers = {
        "Authorization": f"Bearer {token.token}",
        "Content-Type": "application/json",
    }
    
    # Make the GET request
    response = requests.get(url, headers=headers)
    
    # Handle response
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code} - {response.text}")
        response.raise_for_status()

# DatabaseAccounts_Update
# specification/cosmos-db/resource-manager/Microsoft.DocumentDB/stable/2025-04-15/cosmos-db.yaml
def disable_cosmosdb_key_auth(
    subscription_id: str, resource_group: str, cosmosdb_account: str
):
    """Disable key-based authentication for a Cosmos DB account"""
    token = cred.get_token("https://management.azure.com/.default")
    
    # REST API endpoint to update Cosmos DB account properties
    url = f"https://management.azure.com/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.DocumentDB/databaseAccounts/{cosmosdb_account}?api-version=2023-04-15"
    
    headers = {
        "Authorization": f"Bearer {token.token}",
        "Content-Type": "application/json",
    }
    
    # Request body to disable local authentication (key-based access)
    body = {
        "properties": {
            "disableLocalAuth": True
        }
    }
    
    # Make the PATCH request to update the Cosmos DB account
    response = requests.patch(url, headers=headers, json=body)
    
    # Handle response
    if response.status_code in [200, 202]:
        print(f"Successfully disabled key-based auth for Cosmos DB account: {cosmosdb_account}")
        return response.json()
    else:
        print(f"Error: {response.status_code} - {response.text}")
        response.raise_for_status()

# DatabaseAccounts_Update
# specification/cosmos-db/resource-manager/Microsoft.DocumentDB/stable/2025-04-15/cosmos-db.yaml
def enable_cosmosdb_key_auth(
    subscription_id: str, resource_group: str, cosmosdb_account: str
):
    """Enable key-based authentication for a Cosmos DB account"""
    token = cred.get_token("https://management.azure.com/.default")
    
    # REST API endpoint to update Cosmos DB account properties
    url = f"https://management.azure.com/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.DocumentDB/databaseAccounts/{cosmosdb_account}?api-version=2023-04-15"
    
    headers = {
        "Authorization": f"Bearer {token.token}",
        "Content-Type": "application/json",
    }
    
    # Request body to enable local authentication (key-based access)
    body = {
        "properties": {
            "disableLocalAuth": False
        }
    }
    
    # Make the PATCH request to update the Cosmos DB account
    response = requests.patch(url, headers=headers, json=body)
    
    # Handle response
    if response.status_code in [200, 202]:
        print(f"Successfully enabled key-based auth for Cosmos DB account: {cosmosdb_account}")
        return response.json()
    else:
        print(f"Error: {response.status_code} - {response.text}")
        response.raise_for_status()

# DatabaseAccounts_Get
# specification/cosmos-db/resource-manager/Microsoft.DocumentDB/stable/2025-04-15/cosmos-db.yaml
def get_cosmosdb_account_properties(subscription_id, resource_group, account_name):
    """Get Cosmos DB account properties using Azure REST API."""
    # Get access token using Azure Identity
    
    token = cred.get_token("https://management.azure.com/.default")
    
    # Construct the API endpoint
    endpoint = f"https://management.azure.com/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.DocumentDB/databaseAccounts/{account_name}"
    
    # Set up headers with authorization
    headers = {
        "Authorization": f"Bearer {token.token}",
        "Content-Type": "application/json"
    }
    
    # Add API version
    params = {
        "api-version": "2023-04-15"
    }
    
    # Make the request
    response = requests.get(endpoint, headers=headers, params=params)
    response.raise_for_status()
    
    return response.json()
