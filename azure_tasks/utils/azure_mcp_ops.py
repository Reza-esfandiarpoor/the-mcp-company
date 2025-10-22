import asyncio
import json
import os
import xml.etree.ElementTree as ET
from typing import Dict

from fastmcp import Client
from fastmcp.exceptions import ToolError

mcp_url = os.environ.get("AZTASK_MCP_SERVER_URL", "http://localhost:51468/sse")


async def _call_mcp_tool(url: str, name: str, args: Dict):
    client = Client(url)
    async with client:
        await client.ping()
        res = await client.call_tool(name, args)
    return res


def call_mcp_tool(url: str, name: str, args: Dict):
    res = asyncio.run(_call_mcp_tool(url=url, name=name, args=args))
    return res


def call_mcp_tool_parse(url: str, name: str, args: Dict):
    res = asyncio.run(_call_mcp_tool(url=url, name=name, args=args))
    res = res.content[0].text
    try:
        res = json.loads(res)
    except:
        pass
    return res


def list_resources_in_rg(rg_name: str, sub_id: str):
    res = call_mcp_tool(
        url=mcp_url,
        name="resources_Resources_ListByResourceGroup",
        args={"resourceGroupName": rg_name, "subscriptionId": sub_id},
    )
    res = json.loads(res.content[0].text)["value"]
    return res


def create_container(storage_acct, container_name):
    try:
        call_mcp_tool(
            url=mcp_url,
            name="blob_Container_Create",
            args={
                "restype": "container",
                "storage_account": storage_acct,
                "containerName": container_name,
            },
        )
    except ToolError as e:
        if "the specified container already exists".lower() in e.args[0].lower():
            print("Container already exists")
        else:
            raise e


def list_kv_secrets(kv_name: str):
    res = call_mcp_tool(
        url=mcp_url, name="secrets_GetSecrets", args={"vault_name": kv_name}
    )
    secrets = json.loads(res.content[0].text)["value"]
    return secrets


def backup_kv_secret(kv_name, secname):
    res = call_mcp_tool(
        url=mcp_url,
        name="secrets_BackupSecret",
        args={"vault_name": kv_name, "secret-name": secname},
    )
    secval = json.loads(res.content[0].text)["value"]
    return secval


def write_to_blob(storage_acct, container_name, blob_name, data):
    call_mcp_tool(
        url=mcp_url,
        name="blob_BlockBlob_Upload",
        args={
            "storage_account": storage_acct,
            "container_name": container_name,
            "blob_name": blob_name,
            "data": data,
        },
    )


def restore_secret(kvname, value):
    call_mcp_tool(
        url=mcp_url,
        name="secrets_RestoreSecret",
        args={"vault_name": kvname, "value": value},
    )


def translate_text(sub_id, rg_name, translator_acct, src_lang, dst_lang, text):
    res = call_mcp_tool(
        url=mcp_url,
        name="TranslatorText_Translator_Translate",
        args={
            "subscription_id": sub_id,
            "resource_group": rg_name,
            "account_name": translator_acct,
            "source_language": src_lang,
            "target_language": dst_lang,
            "text": text,
        },
    )
    return res.content[0].text


def list_blobs(storage_acct, container_name):
    orig_blobs = call_mcp_tool(
        mcp_url,
        "blob_Container_ListBlobFlatSegment",
        {
            "containerName": container_name,
            "comp": "list",
            "restype": "container",
            "storage_account": storage_acct,
        },
    )
    root = ET.fromstring(orig_blobs.content[0].text)
    orig_blobs = [b.find("Name").text for b in root.findall(".//Blob")]
    return orig_blobs


def read_from_blob(storage_acct, container_name, blob_name):
    txt = call_mcp_tool(
        mcp_url,
        "blob_Blob_Download",
        {
            "storage_account": storage_acct,
            "blob": blob_name,
            "containerName": container_name,
        },
    )
    txt = txt.content[0].text
    return txt


def detect_lang(sub_id, rg_name, translator_acct, text):
    lang = call_mcp_tool(
        mcp_url,
        "TranslatorText_Translator_Detect",
        {
            "subscription_id": sub_id,
            "resource_group": rg_name,
            "account_name": translator_acct,
            "text": text,
        },
    )
    lang = lang.content[0].text
    return lang


def list_kv_locks(sub_id, rg_name, kv_name):
    res = call_mcp_tool(
        mcp_url,
        "locks_ManagementLocks_ListAtResourceLevel",
        {
            "subscriptionId": sub_id,
            "resourceGroupName": rg_name,
            "resourceType": "vaults",
            "parentResourcePath": "",
            "resourceProviderNamespace": "Microsoft.KeyVault",
            "resourceName": kv_name,
        },
    )
    res = json.loads(res.content[0].text)["value"]
    return res


def delete_resource(
    sub_id,
    rg_name,
    resource_provider_namespace,
    resource_type,
    resource_name,
    parent_resource,
    api_v=None,
):
    kwargs = {}
    if api_v is not None:
        kwargs["api-version"] = api_v
    call_mcp_tool(
        mcp_url,
        "resources_Resources_Delete",
        {
            "parentResourcePath": parent_resource,
            "resourceGroupName": rg_name,
            "subscriptionId": sub_id,
            "resourceProviderNamespace": resource_provider_namespace,
            "resourceType": resource_type,
            "resourceName": resource_name,
            **kwargs,
        },
    )


def list_vms(sub_id):
    res = call_mcp_tool(
        mcp_url, "virtualMachine_VirtualMachines_ListAll", {"subscriptionId": sub_id}
    )
    res = json.loads(res.content[0].text)["value"]
    return res


def list_vms_in_rg(sub_id, rg_name):
    res = call_mcp_tool(
        mcp_url,
        "virtualMachine_VirtualMachines_List",
        {"subscriptionId": sub_id, "resourceGroupName": rg_name},
    )
    res = json.loads(res.content[0].text)["value"]
    return res


def ensure_blob_service(sub_id, rg_name, storage_acct, blob_service_name, properties):
    call_mcp_tool(
        mcp_url,
        "blob_BlobServices_SetServiceProperties",
        {
            "resourceGroupName": rg_name,
            "BlobServicesName": blob_service_name,
            "subscriptionId": sub_id,
            "accountName": storage_acct,
            "properties": properties,
        },
    )


def enable_static_website_data_plane(sacct):
    call_mcp_tool(
        mcp_url,
        "blob_Service_SetProperties",
        {
            "comp": "properties",
            "storage_account": sacct,
            "restype": "service",
            "StaticWebsite": {
                "Enabled": True,
                "IndexDocument": "index.html",
                "ErrorDocument404Path": "404.html",
            },
        },
    )


def get_table_entities(storage_acct, table_name):
    res = call_mcp_tool(
        mcp_url,
        "table_Table_QueryEntities",
        {
            "storage_account": storage_acct,
            "table": table_name,
        },
    )
    res = json.loads(res.content[0].text)["value"]
    return res


def insert_row_into_table(storage_acct, table_name, row_data):
    call_mcp_tool(
        mcp_url,
        "table_Table_InsertEntity",
        {
            "storage_account": storage_acct,
            "table_name": table_name,
            "data": row_data,
        },
    )


def ocr_read(vision_acct, url):
    res = call_mcp_tool(
        mcp_url, "Ocr_Read", {"vision_service": vision_acct, "url": url}
    )
    return res.content[0].text
