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
  description = "(Required) Azure region of the Databricks workspace, supplied by azd from AZURE_LOCATION. It must support Unity Gateway and external models. See https://learn.microsoft.com/azure/databricks/resources/feature-region-support."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[a-z0-9]+$", var.location))
    error_message = "The location must be an Azure region name in lowercase without spaces, for example swedencentral."
  }
}

variable "subscription_id" {
  description = "(Required) Azure subscription ID where the Databricks resources are created, supplied by azd from AZURE_SUBSCRIPTION_ID."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", var.subscription_id))
    error_message = "The subscription_id must be a GUID."
  }
}

variable "project_name" {
  description = "(Optional) Short project identifier used in resource names and in the project tag. Defaults to gaig (governed AI gateways)."
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

variable "foundry_account_id" {
  description = "(Required) Resource ID of the Foundry account created by the resources layer, supplied by azd from FOUNDRY_ACCOUNT_ID."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^/subscriptions/[^/]+/resourceGroups/[^/]+/providers/Microsoft.CognitiveServices/accounts/[^/]+$", var.foundry_account_id))
    error_message = "The foundry_account_id must be the resource ID of a Microsoft.CognitiveServices account. Provision the resources layer first."
  }
}

variable "foundry_openai_endpoint" {
  description = "(Required) Azure OpenAI endpoint of the Foundry account, supplied by azd from FOUNDRY_OPENAI_ENDPOINT."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^https://[a-z0-9-]+\\.openai\\.azure\\.com$", var.foundry_openai_endpoint))
    error_message = "The foundry_openai_endpoint must have the form https://<subdomain>.openai.azure.com. Provision the resources layer first."
  }
}

variable "foundry_model_name" {
  description = "(Required) Name of the chat model deployment in Foundry, supplied by azd from FOUNDRY_MODEL_DEPLOYMENT_NAME."
  type        = string
  nullable    = false

  validation {
    condition     = length(trimspace(var.foundry_model_name)) > 0
    error_message = "The foundry_model_name must not be empty. Provision the resources layer first."
  }
}

variable "databricks_catalog_name" {
  description = "(Optional) Unity Catalog catalog that hosts the Unity Gateway objects. When null, the workspace catalog is used; new workspaces get one named after the workspace. Defaults to null."
  type        = string
  default     = null
}

variable "ugw_tokens_per_minute" {
  description = "(Optional) Tokens per minute that each user can consume through the Unity Gateway model provider service. Defaults to 5000, the same budget as the basic product in API Management, so both gateways can be compared."
  type        = number
  default     = 5000
  nullable    = false

  validation {
    condition     = var.ugw_tokens_per_minute > 0
    error_message = "The ugw_tokens_per_minute must be greater than zero."
  }
}
