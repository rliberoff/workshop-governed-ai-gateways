variable "name" {
  description = "(Required) Name and custom subdomain of the Content Safety account. The subdomain must be globally unique."
  type        = string
  nullable    = false
}

variable "location" {
  description = "(Required) Azure region of the Content Safety account."
  type        = string
  nullable    = false
}

variable "resource_group_name" {
  description = "(Required) Name of the resource group that contains the Content Safety account."
  type        = string
  nullable    = false
}

variable "tags" {
  description = "(Required) Tags assigned to the Content Safety account."
  type        = map(string)
  nullable    = false
}
