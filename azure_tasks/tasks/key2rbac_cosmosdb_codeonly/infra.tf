terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.116.0"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = ">= 3.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
  use_cli = true
}

provider "azuread" {
  use_cli = true
}

# --- Look up current tenant/subscription info ---
data "azurerm_client_config" "current" {}
data "azurerm_subscription" "current" {}


# --- Configurable variables ---
variable "location" {
  type    = string
  default = "West US 2"
}

variable "funclocation" {
  type = string
  default = "West Central US"
}

variable "azure_client_id" {
  type        = string
  description = "Azure Service Principal Client ID"
}

data "azuread_service_principal" "sp" {
  client_id = var.azure_client_id
}

# -------------------------
# Resource Group
# -------------------------
resource "azurerm_resource_group" "rg" {
  name     = "azuretasks_key2rbac_cosmosdb_code"
  location = var.location
}


variable "taskstoragename_blob" {
  default = "key2rbaccosmosblbrz3"
}


# Storage Account
resource "azurerm_storage_account" "sa_blob" {
  name                     = var.taskstoragename_blob
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  lifecycle {
    ignore_changes = [
      # Ignore changes to key access since we'll disable it after creation
      shared_access_key_enabled,
      allow_nested_items_to_be_public,
      queue_properties
    ]
  }
}



# Service Plan (Consumption)
resource "azurerm_service_plan" "plan" {
  name                = "func-demo-plan"
  resource_group_name = azurerm_resource_group.rg.name
  #location            = azurerm_resource_group.rg.location
  location            = var.funclocation
  os_type             = "Linux"
  sku_name            = "B1"
  #reserved            = true
}

# Storage Account for Function host
resource "azurerm_storage_account" "funcsa" {
  name                     = "key2rbaccosmosrz3"
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = var.funclocation
  account_tier             = "Standard"
  account_replication_type = "LRS"
  lifecycle {
    ignore_changes = [
      # Ignore changes to key access since we'll disable it after creation
      shared_access_key_enabled,
      allow_nested_items_to_be_public,
      queue_properties
    ]
  }
}

# Cosmos DB Account (Free Tier)
resource "azurerm_cosmosdb_account" "cosmos" {
  name                = "cosmos-code-key2rbac-demo"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  offer_type          = "Standard"
  kind                = "GlobalDocumentDB"
  
  # Enable free tier (limited to one per subscription)
  enable_free_tier = true
  
  consistency_policy {
    consistency_level = "Session"
  }
  
  geo_location {
    location          = azurerm_resource_group.rg.location
    failover_priority = 0
    zone_redundant    = false
  }
}

# Cosmos DB Database
resource "azurerm_cosmosdb_sql_database" "database" {
  name                = "key2rbac-cosmosdb-code-db"
  resource_group_name = azurerm_resource_group.rg.name
  account_name        = azurerm_cosmosdb_account.cosmos.name
}

# Cosmos DB Container
resource "azurerm_cosmosdb_sql_container" "container" {
  name                = "items"
  resource_group_name = azurerm_resource_group.rg.name
  account_name        = azurerm_cosmosdb_account.cosmos.name
  database_name       = azurerm_cosmosdb_sql_database.database.name
  partition_key_path  = "/id"
   # Workaround for provider bug
  lifecycle {
    ignore_changes = [
      partition_key_path
    ]
  }
}

# Function App
resource "azurerm_linux_function_app" "func" {
  name                       = "pyfunc-cosmosdb-code-demorz3"
  resource_group_name        = azurerm_resource_group.rg.name
  location                   = var.funclocation
  service_plan_id            = azurerm_service_plan.plan.id
  storage_account_name       = azurerm_storage_account.funcsa.name
  storage_account_access_key = azurerm_storage_account.funcsa.primary_access_key

  identity {
    type = "SystemAssigned"
  }

  site_config {
    application_stack {
      python_version = "3.9"
    }
  }

  app_settings = {
    "SCM_DO_BUILD_DURING_DEPLOYMENT" = "false"
    "FUNCTIONS_WORKER_RUNTIME" = "python"
    "WEBSITE_RUN_FROM_PACKAGE" = "0"
    "ENABLE_ORYX_BUILD" = "false"
    # Storage info for blob access
    AzureWebJobsStorage        = azurerm_storage_account.sa_blob.primary_connection_string
    FUNCTIONS_EXTENSION_VERSION = "~4"
    # Cosmos DB connection info
    "COSMOS_CONNECTION_STRING" = "AccountEndpoint=${azurerm_cosmosdb_account.cosmos.endpoint};AccountKey=${azurerm_cosmosdb_account.cosmos.primary_key};"
    "COSMOS_KEY"               = azurerm_cosmosdb_account.cosmos.primary_key
    "COSMOS_ENDPOINT"          = azurerm_cosmosdb_account.cosmos.endpoint
    "COSMOS_DATABASE"          = azurerm_cosmosdb_sql_database.database.name
    "COSMOS_CONTAINER"         = azurerm_cosmosdb_sql_container.container.name
  }
}

# Grant the function app's managed identity access to the storage account
resource "azurerm_role_assignment" "func_storage_blob_contributor" {
  scope                = azurerm_storage_account.sa_blob.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_linux_function_app.func.identity[0].principal_id
}

resource "azurerm_cosmosdb_sql_role_assignment" "func_items_rw" {
  resource_group_name = azurerm_resource_group.rg.name
  account_name        = azurerm_cosmosdb_account.cosmos.name

  # Correct data-plane scope path (dbs / colls)
  scope = "${azurerm_cosmosdb_account.cosmos.id}/dbs/${azurerm_cosmosdb_sql_database.database.name}/colls/${azurerm_cosmosdb_sql_container.container.name}"

  role_definition_id  = "${azurerm_cosmosdb_account.cosmos.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002"
  principal_id        = azurerm_linux_function_app.func.identity[0].principal_id
}
