locals {
  # Cognitive Services OpenAI User: inference on the Foundry model deployments, nothing else.
  role_cognitive_services_openai_user = "5e0bd9bd-7b93-4f28-af87-19fc36ad61bd"
}

# Premium workspace: Unity Catalog and Unity Gateway require the Premium tier. New workspaces are enabled for
# Unity Catalog automatically and get a workspace catalog named after the workspace.
resource "azurerm_databricks_workspace" "this" {
  name                          = var.name
  location                      = var.location
  resource_group_name           = var.resource_group_name
  sku                           = "premium"
  managed_resource_group_name   = var.managed_resource_group_name
  public_network_access_enabled = true
  tags                          = var.tags

  lifecycle {
    ignore_changes = [tags]
  }
}

# Access Connector whose managed identity backs the Unity Catalog service credential used by Unity Gateway.
resource "azurerm_databricks_access_connector" "this" {
  name                = var.access_connector_name
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags

  identity {
    type = "SystemAssigned"
  }

  lifecycle {
    ignore_changes = [tags]
  }
}

resource "azurerm_role_assignment" "dbac_foundry_openai_user" {
  scope              = var.foundry_account_id
  role_definition_id = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/${local.role_cognitive_services_openai_user}"
  principal_id       = azurerm_databricks_access_connector.this.identity[0].principal_id
  principal_type     = "ServicePrincipal"
}
