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
# Usage and estimated costs > Custom metrics > With dimensions, expressed as code. azurerm does not expose the
# property and it is missing from the published schema, so azapi_update_resource sets only this property on the
# component; the official sample sets the same property:
# https://github.com/Azure-Samples/AI-Gateway/blob/main/modules/monitor/v1/appinsights.bicep
resource "azapi_update_resource" "custom_metrics_with_dimensions" {
  type        = "Microsoft.Insights/components@2020-02-02"
  resource_id = azurerm_application_insights.this.id

  body = {
    properties = {
      CustomMetricsOptedInType = "WithDimensions"
    }
  }
}
