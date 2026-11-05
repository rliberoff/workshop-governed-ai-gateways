output "id" {
  description = "Resource ID of the Log Analytics workspace."
  value       = azurerm_log_analytics_workspace.this.id
}

output "workspace_id" {
  description = "Workspace (customer) ID used by Log Analytics query clients."
  value       = azurerm_log_analytics_workspace.this.workspace_id
}
