output "id" {
  description = "Resource ID of the Application Insights component."
  value       = azurerm_application_insights.this.id
}

output "connection_string" {
  description = "Connection string of the Application Insights component. It only identifies the ingestion endpoint because local authentication is disabled."
  value       = azurerm_application_insights.this.connection_string
  sensitive   = true
}
