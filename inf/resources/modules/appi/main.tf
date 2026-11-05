# Workspace-based Application Insights for end-to-end traces and the token metrics emitted by API Management:
# client spans, the API Management gateway and the Foundry tracing view. Local authentication is disabled,
# so ingestion requires Microsoft Entra ID.
resource "azurerm_application_insights" "this" {
  name                         = var.name
  location                     = var.location
  resource_group_name          = var.resource_group_name
  workspace_id                 = var.log_analytics_workspace_id
  application_type             = "other"
  local_authentication_enabled = false
  tags                         = var.tags

  lifecycle {
    ignore_changes = [tags]
  }
}

# Custom metrics with dimensions, the prerequisite of the llm-emit-token-metric policy. It is the portal setting
# Usage and estimated costs > Custom metrics > With dimensions, expressed as code, as in the official sample:
# https://github.com/Azure-Samples/AI-Gateway/blob/main/modules/monitor/v1/appinsights.bicep
# azurerm does not expose CustomMetricsOptedInType and it is missing from the AzAPI schema of every API version.
# azapi_update_resource drops properties outside that schema from its PUT, so the setting never reached Azure.
# azapi_resource_action sends the body unfiltered; a PUT replaces the properties, so the body mirrors the
# component that azurerm_application_insights manages.
resource "azapi_resource_action" "custom_metrics_with_dimensions" {
  type        = "Microsoft.Insights/components@2020-02-02"
  resource_id = azurerm_application_insights.this.id
  method      = "PUT"

  body = {
    kind     = azurerm_application_insights.this.application_type
    location = azurerm_application_insights.this.location
    tags     = azurerm_application_insights.this.tags
    properties = {
      Application_Type                = azurerm_application_insights.this.application_type
      WorkspaceResourceId             = azurerm_application_insights.this.workspace_id
      DisableLocalAuth                = !azurerm_application_insights.this.local_authentication_enabled
      DisableIpMasking                = !azurerm_application_insights.this.ip_masking_enabled
      RetentionInDays                 = azurerm_application_insights.this.retention_in_days
      SamplingPercentage              = azurerm_application_insights.this.sampling_percentage
      ForceCustomerStorageForProfiler = azurerm_application_insights.this.force_customer_storage_for_profiler
      publicNetworkAccessForIngestion = azurerm_application_insights.this.internet_ingestion_enabled ? "Enabled" : "Disabled"
      publicNetworkAccessForQuery     = azurerm_application_insights.this.internet_query_enabled ? "Enabled" : "Disabled"
      CustomMetricsOptedInType        = "WithDimensions"
    }
  }
}

# The action never reads the component back, so this check reports when the setting is missing or was changed.
check "custom_metrics_with_dimensions" {
  data "azapi_resource" "appi" {
    type        = "Microsoft.Insights/components@2020-02-02"
    resource_id = azurerm_application_insights.this.id

    response_export_values = {
      custom_metrics_opted_in_type = "properties.CustomMetricsOptedInType"
    }

    depends_on = [azapi_resource_action.custom_metrics_with_dimensions]
  }

  assert {
    condition     = data.azapi_resource.appi.output.custom_metrics_opted_in_type == "WithDimensions"
    error_message = "Application Insights CustomMetricsOptedInType is not WithDimensions, so token metrics lose their dimensions in Azure Metric Store. Do not change Custom metrics in the portal."
  }
}
