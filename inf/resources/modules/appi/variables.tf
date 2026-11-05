variable "name" {
  description = "(Required) Name of the Application Insights component."
  type        = string
  nullable    = false
}

variable "location" {
  description = "(Required) Azure region of the Application Insights component."
  type        = string
  nullable    = false
}

variable "resource_group_name" {
  description = "(Required) Name of the resource group that contains the Application Insights component."
  type        = string
  nullable    = false
}

variable "log_analytics_workspace_id" {
  description = "(Required) Resource ID of the Log Analytics workspace that stores the telemetry."
  type        = string
  nullable    = false
}

variable "tags" {
  description = "(Required) Tags assigned to the Application Insights component."
  type        = map(string)
  nullable    = false
}
