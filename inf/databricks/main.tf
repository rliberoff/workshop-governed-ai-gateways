data "azurerm_client_config" "current" {}

# A new suffix on every recreation keeps Azure from mapping new resources to recently deleted ones.
resource "random_string" "suffix" {
  length  = 6
  upper   = false
  special = false
}

locals {
  name_suffix = "${var.project_name}-${var.environment_id}-${random_string.suffix.result}"

  name_managed_resource_group = "rg-${local.name_suffix}-dbw-managed"
  name_dbw                    = "dbw-${local.name_suffix}"
  name_dbac                   = "dbac-${local.name_suffix}"

  # Unity Catalog names are unique per metastore, which every workspace of the account in the region shares.
  name_service_credential = "${var.project_name}_${var.environment_id}_${random_string.suffix.result}_foundry"

  workspace_catalog_names = toset([replace(local.name_dbw, "-", "_"), "${replace(local.name_dbw, "-", "_")}_${module.dbw.workspace_numeric_id}"])
  catalog_name            = var.databricks_catalog_name != null ? var.databricks_catalog_name : one(setintersection(data.databricks_catalogs.workspace[0].ids, local.workspace_catalog_names))

  tags = merge(var.tags, {
    createdWith = "Terraform"
    createdAt   = "${formatdate("YYYY-MM-DD hh:mm:ss", timestamp())} UTC"
    project     = var.project_name
    environment = var.environment_id
    owner       = data.azurerm_client_config.current.object_id
  })
}

data "azurerm_resource_group" "this" {
  name = var.resource_group_name
}

module "dbw" {
  source = "./modules/dbw"

  name                        = local.name_dbw
  access_connector_name       = local.name_dbac
  location                    = var.location
  resource_group_name         = data.azurerm_resource_group.this.name
  managed_resource_group_name = local.name_managed_resource_group
  subscription_id             = var.subscription_id
  foundry_account_id          = var.foundry_account_id
  deployer_principal_id       = data.azurerm_client_config.current.object_id
  tags                        = local.tags
}

data "databricks_current_user" "deployer" {
  depends_on = [module.dbw]
}

resource "databricks_grant" "deployer_system_catalog" {
  count = var.manage_system_usage_grants ? 1 : 0

  catalog = "system"

  principal  = data.databricks_current_user.deployer.user_name
  privileges = ["USE_CATALOG"]
}

resource "databricks_grant" "deployer_ai_gateway_schema" {
  count = var.manage_system_usage_grants ? 1 : 0

  schema = "system.ai_gateway"

  principal  = data.databricks_current_user.deployer.user_name
  privileges = ["USE_SCHEMA"]

  depends_on = [databricks_grant.deployer_system_catalog]
}

resource "databricks_grant" "deployer_ai_gateway_usage" {
  count = var.manage_system_usage_grants ? 1 : 0

  table = "system.ai_gateway.usage"

  principal  = data.databricks_current_user.deployer.user_name
  privileges = ["SELECT"]

  depends_on = [databricks_grant.deployer_ai_gateway_schema]
}

data "databricks_catalogs" "workspace" {
  count = var.databricks_catalog_name == null ? 1 : 0

  depends_on = [module.dbw]

  lifecycle {
    postcondition {
      condition     = length(setintersection(self.ids, local.workspace_catalog_names)) == 1
      error_message = "Expected exactly one accessible workspace catalog, named after the workspace or suffixed with its numeric ID. Set databricks_catalog_name explicitly if the catalog uses another name."
    }
  }
}

# Resolve the accessible workspace catalog, including the numeric suffix used after a name collision.
data "databricks_catalog" "this" {
  name = local.catalog_name

  depends_on = [module.dbw]
}

# Schema that groups the Unity Gateway objects and the inference table of the workshop.
resource "databricks_schema" "ai_gateway" {
  catalog_name  = data.databricks_catalog.this.name
  name          = "ai_gateway"
  comment       = "Unity Gateway objects of the governed AI gateways workshop."
  force_destroy = true
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
