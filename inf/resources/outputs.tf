# azd stores these UPPER_CASE outputs as environment values. The lab scripts and the databricks layer read
# them from the azd environment. No output carries a secret.

output "AZURE_RESOURCE_GROUP" {
  description = "Name of the resource group of the workshop resources."
  value       = azurerm_resource_group.this.name
}

output "FOUNDRY_ACCOUNT_ID" {
  description = "Resource ID of the Foundry account."
  value       = module.aif.id
}

output "FOUNDRY_ACCOUNT_NAME" {
  description = "Name of the Foundry account."
  value       = module.aif.name
}

output "FOUNDRY_OPENAI_ENDPOINT" {
  description = "Azure OpenAI endpoint of the Foundry account."
  value       = module.aif.openai_endpoint
}

output "FOUNDRY_OPENAI_V1_ENDPOINT" {
  description = "Base URL of the OpenAI v1 API of the Foundry account, used for direct consumption in lab 1."
  value       = module.aif.openai_v1_endpoint
}

output "FOUNDRY_PROJECT_ENDPOINT" {
  description = "Endpoint of the Foundry project used for evaluations, AI red teaming and tracing."
  value       = module.aif.project_endpoint
}

output "FOUNDRY_PROJECT_NAME" {
  description = "Name of the Foundry project of the main account, associated in lab 3 with the API Management AI gateway."
  value       = local.name_proj
}

output "FOUNDRY_STANDALONE_ACCOUNT_ID" {
  description = "Resource ID of the second Foundry account, which gets a standalone AI Gateway in lab 3."
  value       = module.aif_standalone.id
}

output "FOUNDRY_STANDALONE_ACCOUNT_NAME" {
  description = "Name of the second Foundry account, which gets a standalone AI Gateway in lab 3."
  value       = module.aif_standalone.name
}

output "FOUNDRY_STANDALONE_PROJECT_NAME" {
  description = "Name of the Foundry project of the second account."
  value       = local.name_proj_standalone
}

output "FOUNDRY_MODEL_DEPLOYMENT_NAME" {
  description = "Name of the chat model deployment, used as the model field by every client."
  value       = module.aif.model_deployment_name
}

output "APIM_NAME" {
  description = "Name of the API Management instance."
  value       = module.apim.name
}

output "APIM_API_BASE_URL" {
  description = "Base URL of the governed OpenAI v1 API in API Management."
  value       = module.apim.api_base_url
}

output "APIM_SUBSCRIPTION_IDS" {
  description = "JSON map of product ID to API Management subscription ID. The lab scripts read the keys at run time."
  value       = jsonencode(module.apim.subscription_ids)
}

output "LOG_ANALYTICS_WORKSPACE_ID" {
  description = "Workspace ID of the Log Analytics workspace that stores gateway and LLM logs."
  value       = module.log.workspace_id
}
