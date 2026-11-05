# azd stores these UPPER_CASE outputs as environment values; the other layers read them from provider.conf.json.

output "TFSTATE_RESOURCE_GROUP_NAME" {
  description = "Name of the resource group that holds the Terraform remote state."
  value       = azurerm_resource_group.tfstate.name
}

output "TFSTATE_STORAGE_ACCOUNT_NAME" {
  description = "Name of the storage account that holds the Terraform remote state."
  value       = azurerm_storage_account.tfstate.name
}

output "TFSTATE_CONTAINER_NAME" {
  description = "Name of the private blob container that holds the Terraform remote state."
  value       = azurerm_storage_container.tfstate.name
}
