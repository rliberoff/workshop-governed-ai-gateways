# Azure AI Content Safety account used by the llm-content-safety policy of API Management to screen prompts
# (harm categories and Prompt Shields) before they reach the model. Only Microsoft Entra ID is accepted.
resource "azurerm_cognitive_account" "this" {
  name                          = var.name
  location                      = var.location
  resource_group_name           = var.resource_group_name
  kind                          = "ContentSafety"
  sku_name                      = "S0"
  custom_subdomain_name         = var.name
  local_auth_enabled            = false
  public_network_access_enabled = true
  tags                          = var.tags

  lifecycle {
    ignore_changes = [tags]
  }
}
