data "azurerm_client_config" "current" {}

locals {
  name_suffix = "${var.project_name}-${var.environment_id}"

  name_resource_group = "rg-${local.name_suffix}-dbw"
  # Underscores instead of hyphens so the workspace catalog, named after the workspace, needs no quoting in SQL.
  name_dbw  = "dbw_${var.project_name}_${var.environment_id}"
  name_dbac = "dbac-${local.name_suffix}"

  # Unity Catalog names are unique per metastore, which every workspace of the account in the region shares.
  name_service_credential = "${var.project_name}_${var.environment_id}_foundry"

  catalog_name = coalesce(var.databricks_catalog_name, local.name_dbw)

  tags = merge(var.tags, {
    createdWith = "Terraform"
    createdAt   = "${formatdate("YYYY-MM-DD hh:mm:ss", timestamp())} UTC"
    project     = var.project_name
    environment = var.environment_id
    owner       = data.azurerm_client_config.current.object_id
  })
}

resource "azurerm_resource_group" "this" {
  name     = local.name_resource_group
  location = var.location
  tags     = local.tags

  lifecycle {
    ignore_changes = [tags]
  }
}

module "dbw" {
  source = "./modules/dbw"

  name                        = local.name_dbw
  access_connector_name       = local.name_dbac
  location                    = azurerm_resource_group.this.location
  resource_group_name         = azurerm_resource_group.this.name
  managed_resource_group_name = "${local.name_resource_group}-managed"
  subscription_id             = var.subscription_id
  foundry_account_id          = var.foundry_account_id
  tags                        = local.tags
}

# Workspace catalog provisioned by automatic Unity Catalog enablement. The read waits for the workspace,
# because the provider cannot reach a workspace that does not exist yet.
data "databricks_catalog" "this" {
  name = local.catalog_name

  depends_on = [module.dbw]
}

# Schema that groups the Unity Gateway objects and the inference table of the workshop.
resource "databricks_schema" "ai_gateway" {
  catalog_name = data.databricks_catalog.this.name
  name         = "ai_gateway"
  comment      = "Unity Gateway objects of the governed AI gateways workshop."
}

# Unity Catalog service credential backed by the Access Connector managed identity. Unity Gateway obtains
# short-lived Microsoft Entra ID tokens from it, so no Foundry key is stored anywhere. Isolated to this
# workspace because the metastore is shared with other attendees.
resource "databricks_credential" "foundry" {
  name           = local.name_service_credential
  purpose        = "SERVICE"
  isolation_mode = "ISOLATION_MODE_ISOLATED"
  comment        = "Managed identity that Unity Gateway uses to call the Foundry model deployments."

  azure_managed_identity {
    access_connector_id = module.dbw.access_connector_id
  }
}

# Model provider service: the governed entry point of Unity Gateway to the same Foundry deployment that
# API Management exposes. It applies a per-user token limit and logs payloads to an inference table.
resource "databricks_ai_gateway_model_provider_service" "foundry" {
  parent                    = "schemas/${databricks_schema.ai_gateway.catalog_name}.${databricks_schema.ai_gateway.name}"
  model_provider_service_id = "foundry"
  comment                   = "Foundry model deployment governed by Unity Gateway."

  config = {
    provider_type = "EXTERNAL_MODEL_PROVIDER_TYPE_AZURE_OPENAI"

    targets = [{
      model            = var.foundry_model_name
      native_api_types = ["openai/v1/chat/completions"]
    }]

    azure_openai = {
      direct = {
        base_url = var.foundry_openai_endpoint
        service_credential = {
          name = "credentials/${databricks_credential.foundry.name}"
        }
      }
    }

    rate_limits = [{
      key            = "RATE_LIMIT_KEY_USER_DEFAULT"
      renewal_period = "RATE_LIMIT_RENEWAL_PERIOD_MINUTE"
      tokens         = var.ugw_tokens_per_minute
    }]

    inference_table = {
      parent            = "schemas/${databricks_schema.ai_gateway.catalog_name}.${databricks_schema.ai_gateway.name}"
      table_name_prefix = "foundry"
    }
  }
}
