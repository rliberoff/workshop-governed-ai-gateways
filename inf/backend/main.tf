data "azurerm_client_config" "current" {}

locals {
  # A short hash of the subscription keeps globally unique names deterministic without an extra provider.
  name_hash = substr(sha1(var.subscription_id), 0, 6)

  name_resource_group  = "rg-${var.project_name}-tfstate-${var.environment_id}"
  name_storage_account = "st${var.project_name}tf${var.environment_id}${local.name_hash}"

  tags = merge(var.tags, {
    createdWith = "Terraform"
    createdAt   = "${formatdate("YYYY-MM-DD hh:mm:ss", timestamp())} UTC"
    project     = var.project_name
    environment = var.environment_id
    owner       = data.azurerm_client_config.current.object_id
  })
}

# Resource group that only holds the remote state of the other Terraform layers.
resource "azurerm_resource_group" "tfstate" {
  name     = local.name_resource_group
  location = var.location
  tags     = local.tags

  lifecycle {
    ignore_changes = [tags]
  }
}

# Storage account for remote state. Shared keys are disabled, so every access goes through Microsoft Entra ID.
resource "azurerm_storage_account" "tfstate" {
  name                            = local.name_storage_account
  resource_group_name             = azurerm_resource_group.tfstate.name
  location                        = azurerm_resource_group.tfstate.location
  account_kind                    = "StorageV2"
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  https_traffic_only_enabled      = true
  shared_access_key_enabled       = false
  default_to_oauth_authentication = true
  allow_nested_items_to_be_public = false
  tags                            = local.tags

  blob_properties {
    versioning_enabled = true

    delete_retention_policy {
      days = 7
    }

    container_delete_retention_policy {
      days = 7
    }
  }

  lifecycle {
    ignore_changes = [tags]
  }
}

# Private container where each layer stores its state under a per-environment key.
resource "azurerm_storage_container" "tfstate" {
  name                  = "tfstate"
  storage_account_id    = azurerm_storage_account.tfstate.id
  container_access_type = "private"

  depends_on = [azurerm_role_assignment.tfstate_blob_data_contributor]
}

# The caller needs blob data access to read and write state, because Contributor alone grants no data-plane rights.
resource "azurerm_role_assignment" "tfstate_blob_data_contributor" {
  scope                = azurerm_storage_account.tfstate.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = data.azurerm_client_config.current.object_id
}
