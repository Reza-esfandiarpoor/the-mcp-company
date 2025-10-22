"""
Similar to 'azure_tasks/tasks/key2rbac_cosmosdb/mcp_poc.py'
But, we need to disable key-based access for storage instead of cosmosdb, which we can do like the following:

resp = call_mcp_tool_parse(
    mcp_url,
    "storage_StorageAccounts_Update",
    {
        'subscriptionId': sub_id,
        'accountName': 'key2rbacsarz2',
        'resourceGroupName': 'azuretasks_key2rbac',
        'properties': {'properties': {"allowSharedKeyAccess": False}}
    },
)

We can also list storage accounts using 'storage_StorageAccounts_List'
"""
