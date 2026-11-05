variable "name" {
  description = "(Required) Name of the Databricks workspace."
  type        = string
  nullable    = false
}

variable "access_connector_name" {
  description = "(Required) Name of the Databricks Access Connector."
  type        = string
  nullable    = false
}

variable "location" {
  description = "(Required) Azure region of the Databricks workspace and Access Connector."
  type        = string
  nullable    = false
}

variable "resource_group_name" {
  description = "(Required) Name of the resource group that contains the Databricks workspace."
  type        = string
  nullable    = false
}

variable "managed_resource_group_name" {
  description = "(Required) Name of the resource group that Azure Databricks creates and manages for the workspace."
  type        = string
  nullable    = false
}

variable "subscription_id" {
  description = "(Required) Azure subscription ID, used to build built-in role definition IDs."
  type        = string
  nullable    = false
}

variable "foundry_account_id" {
  description = "(Required) Resource ID of the Foundry account the Access Connector identity calls."
  type        = string
  nullable    = false
}

variable "deployer_principal_id" {
  description = "(Required) Microsoft Entra object ID of the Terraform caller. Receives Contributor only on this workspace to allow Databricks workspace administrator access through Azure authentication."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", var.deployer_principal_id))
    error_message = "The deployer_principal_id must be a Microsoft Entra object ID GUID."
  }
}

variable "tags" {
  description = "(Required) Tags assigned to the Databricks resources."
  type        = map(string)
  nullable    = false
}
