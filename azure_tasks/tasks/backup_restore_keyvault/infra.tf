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
resource "azurerm_resource_group" "rg" {
  name     = "azuretasks_backup_restore_keyvault"
  location = var.location
}

variable "taskkvfrom" {
  default = "azuretasks-kv-from"
}
variable "taskkvto" {
  default = "azuretasks-kv-to"
}

# -------------------------
# Key Vault
# -------------------------
resource "azurerm_key_vault" "kv-from" {
  name                        = var.taskkvfrom
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
  scope                = azurerm_key_vault.kv-from.id
}

resource "azurerm_key_vault_secret" "example" {
  name         = "mysecret"
  value        = "super-secret-value"
  key_vault_id = azurerm_key_vault.kv-from.id
}

resource "azurerm_key_vault" "kv-to" {
  # name                        = "azuretasks-kv-to"     # must be globally unique — change if conflict
  name                        = var.taskkvto
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
      "Restore",
      "Delete",
      "List"
    ]
  }
}

# Contributor on the Key Vault resource (RBAC owner)
resource "azurerm_role_assignment" "sp_contributor_kv_to" {
  principal_id         = data.azuread_service_principal.sp.object_id
  role_definition_name = "Contributor"
  scope                = azurerm_key_vault.kv-to.id
}
