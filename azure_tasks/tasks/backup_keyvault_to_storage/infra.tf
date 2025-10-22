terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
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

variable "keyvaultname" {
  default = "azuretasks-kv-read"
}
variable "storageaccountname" {
  default = "backupkvtostoragesa"
}


resource "azurerm_resource_group" "rg" {
  name     = "azuretasks_backup_keyvault_to_storage"
  location = var.location
}

# -------------------------
# Key Vault
# -------------------------
resource "azurerm_key_vault" "kv-read" {
  name                        = var.keyvaultname
  location                    = azurerm_resource_group.rg.location
  resource_group_name         = azurerm_resource_group.rg.name
  tenant_id                   = data.azurerm_client_config.current.tenant_id
  sku_name                    = "standard"

  soft_delete_retention_days  = 7
  purge_protection_enabled    = false

  access_policy {
    tenant_id = data.azurerm_client_config.current.tenant_id
    object_id = data.azuread_service_principal.sp.object_id

    secret_permissions = [
      "Get",
      "Set",
      "Backup",
      "Delete",
      "List"
    ]
  }
}

# Owner on the Key Vault resource (RBAC owner)
resource "azurerm_role_assignment" "sp_contributor_kv_from" {
  principal_id         = data.azuread_service_principal.sp.object_id
  role_definition_name = "Contributor"
  scope                = azurerm_key_vault.kv-read.id
}

resource "azurerm_key_vault_secret" "secret1" {
  name         = "mysecret1"
  value        = "super-secret-value-1"
  key_vault_id = azurerm_key_vault.kv-read.id
}

resource "azurerm_key_vault_secret" "secret2" {
  name         = "mysecret2"
  value        = "super-secret-value-2"
  key_vault_id = azurerm_key_vault.kv-read.id
}

resource "azurerm_key_vault_secret" "secret3" {
  name         = "mysecret3"
  value        = "super-secret-value-3"
  key_vault_id = azurerm_key_vault.kv-read.id
}

# Storage Account
resource "azurerm_storage_account" "sa" {
  # name                     = "backupkvtostoragesa"
  name                     = var.storageaccountname
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

# Role assignment: Storage Blob Data Contributor on storage account
resource "azurerm_role_assignment" "storage_blob_contributor" {
  scope                = azurerm_storage_account.sa.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = data.azuread_service_principal.sp.object_id
}
