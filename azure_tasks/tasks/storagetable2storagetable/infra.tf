terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.49.0"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = ">= 3.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
    azapi = {
      source  = "azure/azapi"
      version = ">=1.5.0"
    } 
  }
}

provider "azurerm" {
  features {}
  #use_cli = true
}

provider "azuread" {
  #use_cli = true
}

provider "azapi" {
}

# --- Look up current tenant/subscription info ---
data "azurerm_client_config" "current" {}
data "azurerm_subscription" "current" {}


# --- Configurable variables ---
variable "location" {
  type    = string
  default = "East US"
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
  name     = "azuretasks_storagetable_to_storagetable"
  location = var.location
}

variable "storageaccountname" {
  default = "table2tablesa"
}

resource "azurerm_storage_account" "sa" {
  # name                     = "table2tablesa" # must be globally unique
  name                     = var.storageaccountname
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

resource "azapi_resource" "table" {
  type      = "Microsoft.Storage/storageAccounts/tableServices/tables@2023-01-01"
  name      = "Table1"
  parent_id = "${azurerm_storage_account.sa.id}/tableServices/default"

  response_export_values = ["*"]
}

resource "azapi_resource" "table2" {
  type      = "Microsoft.Storage/storageAccounts/tableServices/tables@2023-01-01"
  name      = "Table2"
  parent_id = "${azurerm_storage_account.sa.id}/tableServices/default"

  response_export_values = ["*"]
}

resource "azurerm_role_assignment" "storage_table_contributor" {
  scope                = azurerm_storage_account.sa.id
  role_definition_name = "Storage Table Data Contributor"
  principal_id         = data.azuread_service_principal.sp.object_id
}


