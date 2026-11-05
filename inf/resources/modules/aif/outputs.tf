output "id" {
  description = "Resource ID of the Foundry account."
  value       = azurerm_cognitive_account.this.id
}

output "name" {
  description = "Name of the Foundry account."
  value       = azurerm_cognitive_account.this.name
}

output "openai_v1_endpoint" {
  description = "Base URL of the OpenAI v1 API of the Foundry account, without a trailing slash."
  value       = "https://${azurerm_cognitive_account.this.custom_subdomain_name}.services.ai.azure.com/openai/v1"
  ## value       = "https://${azurerm_cognitive_account.this.custom_subdomain_name}.openai.azure.com/openai/v1"

}

output "openai_endpoint" {
  description = "Azure OpenAI endpoint of the Foundry account, as expected by external gateways such as Unity Gateway."
  value       = "https://${azurerm_cognitive_account.this.custom_subdomain_name}.openai.azure.com"
}

output "project_endpoint" {
  description = "Endpoint of the Foundry project used by the Foundry SDK for evaluations and AI red teaming."
  value       = "https://${azurerm_cognitive_account.this.custom_subdomain_name}.services.ai.azure.com/api/projects/${azurerm_cognitive_account_project.this.name}"
}

output "project_principal_id" {
  description = "Principal ID of the system-assigned managed identity of the Foundry project."
  value       = azurerm_cognitive_account_project.this.identity[0].principal_id
}

output "model_deployment_name" {
  description = "Name of the chat model deployment."
  value       = azurerm_cognitive_deployment.this.name
}
