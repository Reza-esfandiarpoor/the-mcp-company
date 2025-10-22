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
  name     = "azuretasks_txt_from_image"
  location = var.location
}

variable "visionname" {
  default = "txtfromimage_vis"
}

variable "visiondomain" {
  default = "txtfromimagevis"
}
variable "taskstoragename" {
  default = "txtfromimagesa"
}

# Azure AI Vision Resource (Free Tier F0)
resource "azurerm_cognitive_account" "vision" {
  # name                = "txtfromimage_vis"
  name                = var.visionname
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  kind                = "ComputerVision"
  sku_name            = "F0" # Free tier
  # custom_subdomain_name = "txtfromimagevis"
  custom_subdomain_name = var.visiondomain
}

# Role assignment: Contributor on Vision resource
resource "azurerm_role_assignment" "vision_contributor" {
  scope                = azurerm_cognitive_account.vision.id
  role_definition_name = "Contributor"
  principal_id         = data.azuread_service_principal.sp.object_id
}

# Role assignment: Contributor on Vision resource
resource "azurerm_role_assignment" "vision_user" {
  scope                = azurerm_cognitive_account.vision.id
  role_definition_name = "Cognitive Services User"
  principal_id         = data.azuread_service_principal.sp.object_id
}




# Storage Account
resource "azurerm_storage_account" "sa" {
  # name                     = "txtfromimagesa"
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
resource "azurerm_storage_container" "container" {
  name                  = "txtfromimagectr"
  storage_account_name  = azurerm_storage_account.sa.name
  container_access_type = "blob" # public read for blobs
}

# Upload image.png
resource "azurerm_storage_blob" "foo" {
  name                   = "image.png"
  storage_account_name   = azurerm_storage_account.sa.name
  storage_container_name = azurerm_storage_container.container.name
  type                   = "Block"
  source                 = "image.png" # must exist locally when running terraform apply
}

