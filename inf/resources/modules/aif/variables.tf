variable "name" {
  description = "(Required) Name and custom subdomain of the Foundry account. The subdomain must be globally unique."
  type        = string
  nullable    = false
}

variable "location" {
  description = "(Required) Azure region of the Foundry account and project."
  type        = string
  nullable    = false
}

variable "resource_group_name" {
  description = "(Required) Name of the resource group that contains the Foundry account."
  type        = string
  nullable    = false
}

variable "project_name" {
  description = "(Required) Name of the Foundry project."
  type        = string
  nullable    = false
}

variable "project_display_name" {
  description = "(Required) Display name of the Foundry project in the Foundry portal."
  type        = string
  nullable    = false
}

variable "project_description" {
  description = "(Required) Description of the Foundry project."
  type        = string
  nullable    = false
}

variable "model" {
  description = "(Required) Chat model to deploy: name, version, deployment SKU and capacity in thousands of tokens per minute."
  type = object({
    name     = string
    version  = string
    sku      = string
    capacity = number
  })
  nullable = false
}

variable "application_insights_id" {
  description = "(Required) Resource ID of the Application Insights component connected to the account and the project."
  type        = string
  nullable    = false
}

variable "application_insights_connection_string" {
  description = "(Required) Connection string of the Application Insights component, sent as a write-only value."
  type        = string
  sensitive   = true
  nullable    = false
}

variable "tags" {
  description = "(Required) Tags assigned to the Foundry account and project."
  type        = map(string)
  nullable    = false
}
