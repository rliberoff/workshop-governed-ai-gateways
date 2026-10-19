variable "environment_id" {
  description = "(Required) Unique developer environment ID, supplied by azd from AZURE_ENV_NAME. It must contain 2-10 lowercase letters or digits and is embedded in every resource name."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[a-z0-9]{2,10}$", var.environment_id))
    error_message = "The environment_id must contain 2-10 lowercase letters or digits."
  }
}

variable "location" {
  description = "(Required) Azure region for the Terraform state resources, supplied by azd from AZURE_LOCATION. See https://learn.microsoft.com/azure/reliability/regions-list."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[a-z0-9]+$", var.location))
    error_message = "The location must be an Azure region name in lowercase without spaces, for example swedencentral."
  }
}

variable "subscription_id" {
  description = "(Required) Azure subscription ID where the state resources are created, supplied by azd from AZURE_SUBSCRIPTION_ID."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", var.subscription_id))
    error_message = "The subscription_id must be a GUID."
  }
}

variable "project_name" {
  description = "(Optional) Short project identifier used in resource names and in the project tag. Defaults to gaig (governed AI gateways). It is limited to four characters so the storage account name stays within 24 characters."
  type        = string
  default     = "gaig"
  nullable    = false

  validation {
    condition     = can(regex("^[a-z0-9]{2,4}$", var.project_name))
    error_message = "The project_name must contain 2-4 lowercase letters or digits."
  }
}

variable "tags" {
  description = "(Optional) Additional tags merged with the mandatory tags on every taggable resource."
  type        = map(string)
  default     = {}
  nullable    = false
}
