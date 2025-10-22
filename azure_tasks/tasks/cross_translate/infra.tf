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
  }
}

provider "azurerm" {
  features {}
  #use_cli = true
}

provider "azuread" {
  #use_cli = true
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
  name     = "azuretasks_cross_translate"
  location = var.location
}

variable "translatename" {
  default = "crosstranslate_translator"
}

variable "translatedomain" {
  default = "crosstranslatetrans"
}
variable "taskstoragename" {
  default = "crosstranslatesa"
}

# -------------------------
# Azure AI Translator
# -------------------------
resource "azurerm_cognitive_account" "translator" {
  # name                = "crosstranslate_translator"
  name                = var.translatename
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  kind                = "TextTranslation"
  sku_name            = "S1" # Pay-as-you-go, $10/Million chars
  # custom_subdomain_name = "crosstranslatetrans"
  custom_subdomain_name = var.translatedomain
}

# Give the SP "Cognitive Services User" on Translator
resource "azurerm_role_assignment" "translator_user" {
  scope                = azurerm_cognitive_account.translator.id
  role_definition_name = "Cognitive Services User"
  principal_id         = data.azuread_service_principal.sp.object_id
}

# Storage Account
resource "azurerm_storage_account" "sa" {
  # name                     = "crosstranslatesa"
  name                     = var.taskstoragename
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

# Storage Container (public access)
resource "azurerm_storage_container" "sort_me" {
  name                  = "sort-me"
  storage_account_name  = azurerm_storage_account.sa.name
  container_access_type = "blob" # public read for blobs
}

resource "azurerm_storage_blob" "doc1" {
  name                   = "doc1.txt"
  storage_account_name   = azurerm_storage_account.sa.name
  storage_container_name = azurerm_storage_container.sort_me.name
  type                   = "Block"
  source                 = "doc1.txt" # must exist locally when running terraform apply
}

resource "azurerm_storage_blob" "doc2" {
  name                   = "doc2.txt"
  storage_account_name   = azurerm_storage_account.sa.name
  storage_container_name = azurerm_storage_container.sort_me.name
  type                   = "Block"
  source                 = "doc2.txt" # must exist locally when running terraform apply
}

resource "azurerm_storage_blob" "doc3" {
  name                   = "doc3.txt"
  storage_account_name   = azurerm_storage_account.sa.name
  storage_container_name = azurerm_storage_container.sort_me.name
  type                   = "Block"
  source                 = "doc3.txt" # must exist locally when running terraform apply
}




resource "azurerm_storage_blob" "doc4" {
  name                   = "doc4.txt"
  storage_account_name   = azurerm_storage_account.sa.name
  storage_container_name = azurerm_storage_container.sort_me.name
  type                   = "Block"
  source                 = "doc4.txt" # must exist locally when running terraform apply
}

