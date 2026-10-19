locals {
  # Built-in role definition IDs. IDs are used instead of names because Foundry roles were renamed recently.
  role_cognitive_services_openai_user = "5e0bd9bd-7b93-4f28-af87-19fc36ad61bd"
  role_cognitive_services_user        = "a97b65f3-24c7-4388-baec-2e87135dc908"
  role_monitoring_metrics_publisher   = "3913510d-42f4-4e42-8a64-420c390055eb"

  role_definition_id_prefix = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions"

  api_name                  = "foundry-openai-v1"
  foundry_backend_name      = "foundry-openai-v1"
  content_safety_backend_id = "content-safety"

  # Metric namespace of the llm-emit-token-metric policy in Application Insights.
  token_metric_namespace = "governed-ai-gateways"
}

# API Management v2 instance acting as the enterprise AI gateway.
resource "azurerm_api_management" "this" {
  name                = var.name
  location            = var.location
  resource_group_name = var.resource_group_name
  publisher_name      = var.publisher_name
  publisher_email     = var.publisher_email
  sku_name            = var.sku_name
  tags                = var.tags

  identity {
    type = "SystemAssigned"
  }

  lifecycle {
    ignore_changes = [tags]
  }
}

# The gateway identity calls the model deployments in Foundry.
resource "azurerm_role_assignment" "apim_foundry_openai_user" {
  scope              = var.foundry_account_id
  role_definition_id = "${local.role_definition_id_prefix}/${local.role_cognitive_services_openai_user}"
  principal_id       = azurerm_api_management.this.identity[0].principal_id
  principal_type     = "ServicePrincipal"
}

# The llm-content-safety policy requires Cognitive Services User on the Content Safety account.
resource "azurerm_role_assignment" "apim_content_safety_user" {
  scope              = var.content_safety_id
  role_definition_id = "${local.role_definition_id_prefix}/${local.role_cognitive_services_user}"
  principal_id       = azurerm_api_management.this.identity[0].principal_id
  principal_type     = "ServicePrincipal"
}

# Application Insights has local authentication disabled, so the gateway publishes telemetry with its identity.
resource "azurerm_role_assignment" "apim_appi_metrics_publisher" {
  scope              = var.application_insights_id
  role_definition_id = "${local.role_definition_id_prefix}/${local.role_monitoring_metrics_publisher}"
  principal_id       = azurerm_api_management.this.identity[0].principal_id
  principal_type     = "ServicePrincipal"
}

# Backend for the OpenAI v1 API of Foundry. The circuit breaker opens for one minute after three throttled
# or failed responses in one minute, and honors Retry-After, protecting both the model quota and the callers.
resource "azurerm_api_management_backend" "foundry" {
  name                = local.foundry_backend_name
  resource_group_name = var.resource_group_name
  api_management_name = azurerm_api_management.this.name
  protocol            = "http"
  url                 = var.foundry_openai_v1_endpoint
  description         = "Microsoft Foundry OpenAI v1 endpoint"

  circuit_breaker_rule {
    name                       = "foundry-throttling-or-failure"
    trip_duration              = "PT1M"
    accept_retry_after_enabled = true

    failure_condition {
      count             = 3
      interval_duration = "PT1M"

      status_code_range {
        min = 429
        max = 429
      }

      status_code_range {
        min = 500
        max = 599
      }
    }
  }
}

# Backend for Azure AI Content Safety. azapi is required because the llm-content-safety policy needs managed
# identity credentials on the backend, a property that azurerm does not expose and that is missing from the
# published schema; schema validation is therefore disabled. Same contract as the official sample:
# https://github.com/Azure-Samples/AI-Gateway/blob/main/labs/content-safety/main.bicep
resource "azapi_resource" "content_safety_backend" {
  type                      = "Microsoft.ApiManagement/service/backends@2024-06-01-preview"
  name                      = local.content_safety_backend_id
  parent_id                 = azurerm_api_management.this.id
  schema_validation_enabled = false

  body = {
    properties = {
      description = "Azure AI Content Safety endpoint"
      url         = var.content_safety_endpoint
      protocol    = "http"
      credentials = {
        managedIdentity = {
          resource = "https://cognitiveservices.azure.com"
        }
      }
    }
  }
}

# OpenAI v1 API imported from a minimal OpenAPI definition. Consumers send their subscription key in the
# api-key header, the same header that OpenAI-compatible SDKs use for Azure endpoints.
resource "azurerm_api_management_api" "foundry" {
  name                  = local.api_name
  resource_group_name   = var.resource_group_name
  api_management_name   = azurerm_api_management.this.name
  revision              = "1"
  display_name          = "Microsoft Foundry (OpenAI v1)"
  path                  = var.api_path
  protocols             = ["https"]
  subscription_required = true

  subscription_key_parameter_names {
    header = "api-key"
    query  = "api-key"
  }

  import {
    content_format = "openapi+json"
    content_value  = file("${path.module}/specs/openai-v1.json")
  }
}

resource "azurerm_api_management_api_policy" "foundry" {
  api_name            = azurerm_api_management_api.foundry.name
  api_management_name = azurerm_api_management.this.name
  resource_group_name = var.resource_group_name

  xml_content = templatefile("${path.module}/policies/api.xml.tftpl", {
    foundry_backend_id        = azurerm_api_management_backend.foundry.name
    token_metric_namespace    = local.token_metric_namespace
    content_safety_enabled    = var.content_safety_enabled
    content_safety_backend_id = azapi_resource.content_safety_backend.name
    content_safety_thresholds = var.content_safety_thresholds
  })
}

# One product per consumer tier. Access control starts here: without an active subscription there is no access.
resource "azurerm_api_management_product" "this" {
  for_each = var.products

  product_id            = each.key
  resource_group_name   = var.resource_group_name
  api_management_name   = azurerm_api_management.this.name
  display_name          = each.value.display_name
  description           = each.value.description
  subscription_required = true
  approval_required     = false
  published             = true
}

resource "azurerm_api_management_product_api" "this" {
  for_each = var.products

  api_name            = azurerm_api_management_api.foundry.name
  product_id          = azurerm_api_management_product.this[each.key].product_id
  api_management_name = azurerm_api_management.this.name
  resource_group_name = var.resource_group_name
}

resource "azurerm_api_management_product_policy" "this" {
  for_each = var.products

  product_id          = azurerm_api_management_product.this[each.key].product_id
  api_management_name = azurerm_api_management.this.name
  resource_group_name = var.resource_group_name

  xml_content = templatefile("${path.module}/policies/product.xml.tftpl", {
    token_limit_enabled = var.token_limit_enabled
    tokens_per_minute   = each.value.tokens_per_minute
    token_quota         = each.value.token_quota
    token_quota_period  = each.value.token_quota_period
  })
}

# One subscription per product. The keys are generated by API Management; the lab scripts read them at run
# time through the management API instead of exposing them as outputs.
resource "azurerm_api_management_subscription" "this" {
  for_each = var.products

  subscription_id     = "app-${each.key}"
  display_name        = "App ${each.value.display_name}"
  resource_group_name = var.resource_group_name
  api_management_name = azurerm_api_management.this.name
  product_id          = azurerm_api_management_product.this[each.key].id
  state               = "active"
  allow_tracing       = false
}

# Resource logs and platform metrics of the instance go to resource-specific tables such as
# ApiManagementGatewayLogs.
resource "azurerm_monitor_diagnostic_setting" "apim" {
  name                           = "diag-${var.name}"
  target_resource_id             = azurerm_api_management.this.id
  log_analytics_workspace_id     = var.log_analytics_workspace_id
  log_analytics_destination_type = "Dedicated"

  enabled_log {
    category_group = "allLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}

# Application Insights logger authenticated with the gateway identity.
resource "azurerm_api_management_logger" "appi" {
  name                = "appi"
  api_management_name = azurerm_api_management.this.name
  resource_group_name = var.resource_group_name
  resource_id         = var.application_insights_id
  buffered            = false

  application_insights {
    connection_string  = var.application_insights_connection_string
    identity_client_id = "SystemAssigned"
  }

  depends_on = [azurerm_role_assignment.apim_appi_metrics_publisher]
}

# Application Insights diagnostic of the API: W3C trace context correlation, so gateway requests join the traces
# started by the client application, and "metrics": true, which the built-in llm-emit-token-metric policy needs
# to publish its token metrics. azapi is required because azurerm does not expose the metrics property:
# https://learn.microsoft.com/azure/api-management/api-management-howto-app-insights#emit-custom-metrics
resource "azapi_resource" "api_diagnostic_appi" {
  type      = "Microsoft.ApiManagement/service/apis/diagnostics@2024-06-01-preview"
  name      = "applicationinsights"
  parent_id = "${azurerm_api_management.this.id}/apis/${azurerm_api_management_api.foundry.name}"

  body = {
    properties = {
      loggerId                = azurerm_api_management_logger.appi.id
      alwaysLog               = "allErrors"
      httpCorrelationProtocol = "W3C"
      logClientIp             = false
      metrics                 = true
      operationNameFormat     = "Name"
      verbosity               = "information"
      sampling = {
        samplingType = "fixed"
        percentage   = 100
      }
    }
  }
}

# Azure Monitor logger of the instance. azurerm cannot manage loggers of type azureMonitor, and the logger may
# already exist on the instance, so an idempotent PUT action is used instead of a managed resource.
resource "azapi_resource_action" "azure_monitor_logger" {
  type        = "Microsoft.ApiManagement/service/loggers@2024-06-01-preview"
  resource_id = "${azurerm_api_management.this.id}/loggers/azuremonitor"
  method      = "PUT"

  body = {
    properties = {
      loggerType = "azureMonitor"
      isBuffered = false
    }
  }
}

# Azure Monitor diagnostic of the API: gateway requests, status codes and error reasons in the
# ApiManagementGatewayLogs resource log table, without request or response bodies.
resource "azurerm_api_management_api_diagnostic" "azure_monitor" {
  identifier               = "azuremonitor"
  resource_group_name      = var.resource_group_name
  api_management_name      = azurerm_api_management.this.name
  api_name                 = azurerm_api_management_api.foundry.name
  api_management_logger_id = azapi_resource_action.azure_monitor_logger.id
  sampling_percentage      = 100
  always_log_errors        = true
  log_client_ip            = false
  verbosity                = "information"
}
