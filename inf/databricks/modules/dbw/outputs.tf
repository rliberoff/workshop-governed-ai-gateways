output "workspace_id" {
  description = "Azure resource ID of the Databricks workspace."
  value       = azurerm_databricks_workspace.this.id
}

output "workspace_url" {
  description = "HTTPS URL of the Databricks workspace."
  value       = "https://${azurerm_databricks_workspace.this.workspace_url}"
}

output "access_connector_id" {
  description = "Resource ID of the Databricks Access Connector."
  value       = azurerm_databricks_access_connector.this.id
}
