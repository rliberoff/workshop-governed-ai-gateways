# azd stores these UPPER_CASE outputs as environment values for the Unity Gateway lab script.

output "DATABRICKS_RESOURCE_GROUP" {
  description = "Name of the resource group of the Databricks workspace."
  value       = azurerm_resource_group.this.name
}

output "DATABRICKS_WORKSPACE_URL" {
  description = "URL of the Databricks workspace."
  value       = module.dbw.workspace_url
}

output "DATABRICKS_WORKSPACE_RESOURCE_ID" {
  description = "Azure resource ID of the Databricks workspace, used for Microsoft Entra ID authentication."
  value       = module.dbw.workspace_id
}

output "DATABRICKS_MODEL_PROVIDER_SERVICE" {
  description = "Three-part name of the Unity Gateway model provider service, sent in the Databricks-Model-Provider-Service header."
  value       = "${databricks_schema.ai_gateway.catalog_name}.${databricks_schema.ai_gateway.name}.${databricks_ai_gateway_model_provider_service.foundry.model_provider_service_id}"
}

output "DATABRICKS_SCHEMA" {
  description = "Catalog and schema that contain the Unity Gateway objects and the inference table."
  value       = "${databricks_schema.ai_gateway.catalog_name}.${databricks_schema.ai_gateway.name}"
}
