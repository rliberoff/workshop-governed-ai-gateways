# Shared Log Analytics workspace: API Management resource logs (including LLM prompts and completions)
# and the workspace-based Application Insights component both land here.
resource "azurerm_log_analytics_workspace" "this" {
  name                = var.name
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "PerGB2018"
  retention_in_days   = var.retention_in_days
  tags                = var.tags

  lifecycle {
    ignore_changes = [tags]
  }
}
