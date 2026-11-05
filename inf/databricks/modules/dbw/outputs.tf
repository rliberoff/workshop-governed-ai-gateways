output "workspace_id" {
  description = "Azure resource ID of the Databricks workspace."
  value       = azurerm_databricks_workspace.this.id

  depends_on = [azurerm_role_assignment.deployer_workspace_contributor]
}

output "workspace_numeric_id" {
  description = "Numeric Databricks workspace ID used to identify its automatically provisioned catalog."
  value       = azurerm_databricks_workspace.this.workspace_id
}

output "workspace_url" {
  description = "HTTPS URL of the Databricks workspace."
  value       = "https://${azurerm_databricks_workspace.this.workspace_url}"

  depends_on = [azurerm_role_assignment.deployer_workspace_contributor]
}

output "access_connector_id" {
  description = "Resource ID of the Databricks Access Connector."
  value       = azurerm_databricks_access_connector.this.id
}
