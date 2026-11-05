output "name" {
  description = "Name of the API Management instance."
  value       = azurerm_api_management.this.name
}

output "gateway_url" {
  description = "Gateway URL of the API Management instance."
  value       = azurerm_api_management.this.gateway_url
}

output "api_base_url" {
  description = "Base URL of the governed OpenAI v1 API, without a trailing slash."
  value       = "${azurerm_api_management.this.gateway_url}/${azurerm_api_management_api.foundry.path}"
}

output "subscription_ids" {
  description = "Map of product ID to API Management subscription ID. The keys themselves are never exported."
  value       = { for product_id, subscription in azurerm_api_management_subscription.this : product_id => subscription.subscription_id }
}
