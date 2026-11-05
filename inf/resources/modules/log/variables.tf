variable "name" {
  description = "(Required) Name of the Log Analytics workspace."
  type        = string
  nullable    = false
}

variable "location" {
  description = "(Required) Azure region of the Log Analytics workspace."
  type        = string
  nullable    = false
}

variable "resource_group_name" {
  description = "(Required) Name of the resource group that contains the Log Analytics workspace."
  type        = string
  nullable    = false
}

variable "retention_in_days" {
  description = "(Required) Data retention in days."
  type        = number
  nullable    = false
}

variable "tags" {
  description = "(Required) Tags assigned to the Log Analytics workspace."
  type        = map(string)
  nullable    = false
}
