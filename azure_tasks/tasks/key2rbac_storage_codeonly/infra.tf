terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100.0"
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
  default = "East US"
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
  name     = "azuretasks_key2rbac_storage_codeonly"
  location = var.location
}


variable "taskstoragename_blob" {
  default = "key2rbacstrgcodesarz4"
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

# Blob container
resource "azurerm_storage_container" "container" {
  name                  = "input"
  storage_account_name  = azurerm_storage_account.sa_blob.name
  container_access_type = "private"
}

# Role assignment: Storage Blob Data Contributor on storage account
resource "azurerm_role_assignment" "storage_blob_contributor" {
  scope                = azurerm_storage_account.sa_blob.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = data.azuread_service_principal.sp.object_id
}

# Upload image.png
resource "azurerm_storage_blob" "foo" {
  name                   = "foo.txt"
  storage_account_name   = azurerm_storage_account.sa_blob.name
  storage_container_name = azurerm_storage_container.container.name
  type                   = "Block"
  source                 = "foo.txt" # must exist locally when running terraform apply
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
  name                     = "funcstractdemo123rz4"
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}


# Function App
resource "azurerm_linux_function_app" "func" {
  name                       = "pyfunc-blob-demo-coderz4"
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
    "BLOB_ACCOUNT_NAME"        = azurerm_storage_account.sa_blob.name
    "BLOB_ACCOUNT_KEY"         = azurerm_storage_account.sa_blob.primary_access_key
    "BLOB_CONTAINER"           = azurerm_storage_container.container.name
    "BLOB_NAME"                = azurerm_storage_blob.foo.name
    AzureWebJobsStorage        = azurerm_storage_account.sa_blob.primary_connection_string
    FUNCTIONS_EXTENSION_VERSION = "~4"
  }

}

# Grant the function app's managed identity access to the storage account
resource "azurerm_role_assignment" "func_storage_blob_contributor" {
  scope                = azurerm_storage_account.sa_blob.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_linux_function_app.func.identity[0].principal_id
}

