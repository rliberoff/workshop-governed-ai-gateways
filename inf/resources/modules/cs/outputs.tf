output "id" {
  description = "Resource ID of the Content Safety account."
  value       = azurerm_cognitive_account.this.id
}

output "endpoint" {
  description = "Endpoint of the Content Safety account, without a trailing slash, as required by the API Management backend."
  value       = trimsuffix(azurerm_cognitive_account.this.endpoint, "/")
}
