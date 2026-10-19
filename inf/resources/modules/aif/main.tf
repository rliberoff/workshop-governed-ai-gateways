# Microsoft Foundry account (kind AIServices) with project management enabled.
# Local authentication is disabled: every caller, including the AI gateways, must use Microsoft Entra ID.
resource "azurerm_cognitive_account" "this" {
  name                          = var.name
  location                      = var.location
  resource_group_name           = var.resource_group_name
  kind                          = "AIServices"
  sku_name                      = "S0"
  custom_subdomain_name         = var.name
  project_management_enabled    = true
  local_auth_enabled            = false
  public_network_access_enabled = true
  tags                          = var.tags

  identity {
    type = "SystemAssigned"
  }

  lifecycle {
    ignore_changes = [tags]
  }
}

# Foundry project that hosts evaluations, AI red teaming results and the tracing view.
resource "azurerm_cognitive_account_project" "this" {
  name                 = var.project_name
  cognitive_account_id = azurerm_cognitive_account.this.id
  location             = var.location
  display_name         = var.project_display_name
  description          = var.project_description
  tags                 = var.tags

  identity {
    type = "SystemAssigned"
  }

  lifecycle {
    ignore_changes = [tags]
  }
}

# Chat model deployment. The deployment name equals the model name so every gateway exposes the same model ID.
resource "azurerm_cognitive_deployment" "this" {
  name                   = var.model.name
  cognitive_account_id   = azurerm_cognitive_account.this.id
  version_upgrade_option = "NoAutoUpgrade"

  model {
    format  = "OpenAI"
    name    = var.model.name
    version = var.model.version
  }

  sku {
    name     = var.model.sku
    capacity = var.model.capacity
  }
}

# Application Insights connections at account and project level, following the official Foundry template:
# https://github.com/microsoft-foundry/foundry-samples/blob/main/infrastructure/infrastructure-setup-bicep/01-connections/connection-application-insights.bicep
# azapi is used because azurerm has no project-level connection resource, and because sensitive_body is
# write-only: the connection string is sent to Azure but never stored in the Terraform state.
resource "azapi_resource" "account_connection_appi" {
  type      = "Microsoft.CognitiveServices/accounts/connections@2025-06-01"
  name      = "${var.name}-appi"
  parent_id = azurerm_cognitive_account.this.id

  body = {
    properties = {
      category      = "AppInsights"
      target        = var.application_insights_id
      authType      = "ApiKey"
      isSharedToAll = true
      metadata = {
        ApiType    = "Azure"
        ResourceId = var.application_insights_id
      }
    }
  }

  sensitive_body = {
    properties = {
      credentials = {
        key = var.application_insights_connection_string
      }
    }
  }
}

resource "azapi_resource" "project_connection_appi" {
  type      = "Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01"
  name      = "${var.project_name}-appi"
  parent_id = azurerm_cognitive_account_project.this.id

  body = {
    properties = {
      category      = "AppInsights"
      target        = var.application_insights_id
      authType      = "ApiKey"
      isSharedToAll = true
      metadata = {
        ApiType    = "Azure"
        ResourceId = var.application_insights_id
      }
    }
  }

  sensitive_body = {
    properties = {
      credentials = {
        key = var.application_insights_connection_string
      }
    }
  }
}
