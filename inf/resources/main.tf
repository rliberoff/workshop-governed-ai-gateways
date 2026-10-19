data "azurerm_client_config" "current" {}

locals {
  # A short hash of the subscription keeps globally unique names deterministic without an extra provider.
  name_hash   = substr(sha1(var.subscription_id), 0, 6)
  name_suffix = "${var.project_name}-${var.environment_id}"

  name_resource_group  = "rg-${local.name_suffix}"
  name_log             = "log-${local.name_suffix}"
  name_appi            = "appi-${local.name_suffix}"
  name_aif             = "aif-${local.name_suffix}-${local.name_hash}"
  name_proj            = "proj-${local.name_suffix}"
  name_aif_standalone  = "aif-${local.name_suffix}-sa-${local.name_hash}"
  name_proj_standalone = "proj-${local.name_suffix}-sa"
  name_cs              = "cs-${local.name_suffix}-${local.name_hash}"
  name_apim            = "apim-${local.name_suffix}-${local.name_hash}"

  # Base path of the governed API in API Management. Clients append /chat/completions or /responses.
  apim_api_path = "foundry/openai/v1"

  # Built-in role definition IDs. IDs are used instead of names because Foundry roles were renamed recently.
  role_foundry_user                 = "53ca6127-db72-4b80-b1b0-d745d6d5456d"
  role_log_analytics_reader         = "73c42c96-874c-492b-b04d-ab87d138a893"
  role_monitoring_metrics_publisher = "3913510d-42f4-4e42-8a64-420c390055eb"

  role_definition_id_prefix = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions"

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

module "log" {
  source = "./modules/log"

  name                = local.name_log
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  retention_in_days   = var.log_retention_in_days
  tags                = local.tags
}

module "appi" {
  source = "./modules/appi"

  name                       = local.name_appi
  location                   = azurerm_resource_group.this.location
  resource_group_name        = azurerm_resource_group.this.name
  log_analytics_workspace_id = module.log.id
  tags                       = local.tags
}

module "aif" {
  source = "./modules/aif"

  name                                   = local.name_aif
  location                               = azurerm_resource_group.this.location
  resource_group_name                    = azurerm_resource_group.this.name
  project_name                           = local.name_proj
  project_display_name                   = "Governed AI gateways workshop"
  project_description                    = "Evaluations, AI red teaming and traces of the governed AI gateways workshop."
  model                                  = var.aif_model
  application_insights_id                = module.appi.id
  application_insights_connection_string = module.appi.connection_string
  tags                                   = local.tags
}

# Second Foundry account for lab 3. A Foundry account supports a single AI Gateway, so showing both modes needs
# two accounts: this one gets a standalone AI Gateway, for which Foundry creates its own API Management
# instance, while the main account is associated with the API Management instance of this layer. Both
# associations are made in the Foundry portal, the only documented way to enable an AI Gateway on an account.
module "aif_standalone" {
  source = "./modules/aif"

  name                                   = local.name_aif_standalone
  location                               = azurerm_resource_group.this.location
  resource_group_name                    = azurerm_resource_group.this.name
  project_name                           = local.name_proj_standalone
  project_display_name                   = "Standalone AI Gateway workshop"
  project_description                    = "Project governed by a standalone Foundry AI Gateway in the governed AI gateways workshop."
  model                                  = merge(var.aif_model, { capacity = var.aif_standalone_model_capacity })
  application_insights_id                = module.appi.id
  application_insights_connection_string = module.appi.connection_string
  tags                                   = local.tags
}

module "cs" {
  source = "./modules/cs"

  name                = local.name_cs
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  tags                = local.tags
}

module "apim" {
  source = "./modules/apim"

  name                                   = local.name_apim
  location                               = azurerm_resource_group.this.location
  resource_group_name                    = azurerm_resource_group.this.name
  subscription_id                        = var.subscription_id
  publisher_name                         = var.apim_publisher_name
  publisher_email                        = var.apim_publisher_email
  sku_name                               = var.apim_sku_name
  api_path                               = local.apim_api_path
  foundry_account_id                     = module.aif.id
  foundry_openai_v1_endpoint             = module.aif.openai_v1_endpoint
  content_safety_id                      = module.cs.id
  content_safety_endpoint                = module.cs.endpoint
  content_safety_enabled                 = var.apim_content_safety_enabled
  content_safety_thresholds              = var.apim_content_safety_thresholds
  token_limit_enabled                    = var.apim_token_limit_enabled
  products                               = var.apim_products
  log_analytics_workspace_id             = module.log.id
  application_insights_id                = module.appi.id
  application_insights_connection_string = module.appi.connection_string
  tags                                   = local.tags
}

# The workshop attendee calls the model directly in lab 1 and runs evaluations and AI red teaming,
# so the deploying identity needs Foundry User at account scope; a project-only assignment does not
# authorize model inference.
resource "azurerm_role_assignment" "caller_foundry_user" {
  scope              = module.aif.id
  role_definition_id = "${local.role_definition_id_prefix}/${local.role_foundry_user}"
  principal_id       = data.azurerm_client_config.current.object_id
}

# The attendee tries the standalone AI Gateway project in the Foundry portal and its model deployment.
resource "azurerm_role_assignment" "caller_foundry_standalone_user" {
  scope              = module.aif_standalone.id
  role_definition_id = "${local.role_definition_id_prefix}/${local.role_foundry_user}"
  principal_id       = data.azurerm_client_config.current.object_id
}

# Cloud evaluations invoke the judge model with the project managed identity.
resource "azurerm_role_assignment" "project_foundry_user" {
  scope              = module.aif.id
  role_definition_id = "${local.role_definition_id_prefix}/${local.role_foundry_user}"
  principal_id       = module.aif.project_principal_id
  principal_type     = "ServicePrincipal"
}

# The lab scripts export client-side spans with Microsoft Entra ID, because local authentication is disabled.
resource "azurerm_role_assignment" "caller_appi_metrics_publisher" {
  scope              = module.appi.id
  role_definition_id = "${local.role_definition_id_prefix}/${local.role_monitoring_metrics_publisher}"
  principal_id       = data.azurerm_client_config.current.object_id
}

# Querying gateway logs and traces needs Log Analytics Reader on the workspace and on Application Insights.
resource "azurerm_role_assignment" "caller_log_reader" {
  scope              = module.log.id
  role_definition_id = "${local.role_definition_id_prefix}/${local.role_log_analytics_reader}"
  principal_id       = data.azurerm_client_config.current.object_id
}

resource "azurerm_role_assignment" "caller_appi_log_reader" {
  scope              = module.appi.id
  role_definition_id = "${local.role_definition_id_prefix}/${local.role_log_analytics_reader}"
  principal_id       = data.azurerm_client_config.current.object_id
}
