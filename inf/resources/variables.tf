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
  description = "(Required) Azure region for every resource, supplied by azd from AZURE_LOCATION. It must support Foundry evaluations, the AI Red Teaming Agent and the selected model; swedencentral supports all of them. See https://learn.microsoft.com/azure/foundry/concepts/evaluation-regions-limits-virtual-network."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[a-z0-9]+$", var.location))
    error_message = "The location must be an Azure region name in lowercase without spaces, for example swedencentral."
  }
}

variable "subscription_id" {
  description = "(Required) Azure subscription ID where the resources are created, supplied by azd from AZURE_SUBSCRIPTION_ID."
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

variable "log_retention_in_days" {
  description = "(Optional) Retention in days of the Log Analytics workspace that stores gateway and LLM logs. Defaults to 30, the minimum billable retention."
  type        = number
  default     = 30
  nullable    = false

  validation {
    condition     = var.log_retention_in_days >= 30 && var.log_retention_in_days <= 730
    error_message = "The log_retention_in_days must be between 30 and 730."
  }
}

variable "aif_model" {
  description = "(Optional) Chat model deployed in the Foundry account. The deployment uses the model name, so clients send it as the model field. Defaults to gpt-6-luna 2026-09-22 with GlobalStandard and 50K tokens per minute. Check availability with 'az cognitiveservices model list --location <region>'."
  type = object({
    name     = string
    version  = string
    sku      = string
    capacity = number
  })
  default = {
    name     = "gpt-6-luna"
    version  = "2026-09-22"
    sku      = "GlobalStandard"
    capacity = 50
  }
  nullable = false

  validation {
    condition     = contains(["GlobalStandard", "DataZoneStandard", "Standard"], var.aif_model.sku)
    error_message = "The aif_model.sku must be GlobalStandard, DataZoneStandard or Standard."
  }

  validation {
    condition     = var.aif_model.capacity >= 1 && var.aif_model.capacity <= 1000
    error_message = "The aif_model.capacity, in thousands of tokens per minute, must be between 1 and 1000."
  }
}

variable "aif_standalone_model_capacity" {
  description = "(Optional) Capacity, in thousands of tokens per minute, of the model deployment in the second Foundry account used for the standalone AI Gateway of lab 3. It uses the same model as aif_model. Defaults to 10, enough for the lab and small enough to save quota."
  type        = number
  default     = 10
  nullable    = false

  validation {
    condition     = var.aif_standalone_model_capacity >= 1 && var.aif_standalone_model_capacity <= 1000
    error_message = "The aif_standalone_model_capacity must be between 1 and 1000."
  }
}

variable "apim_publisher_email" {
  description = "(Required) Email address that API Management uses as publisher contact and for service notifications. Set it with 'azd env set APIM_PUBLISHER_EMAIL <email>'."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.apim_publisher_email))
    error_message = "The apim_publisher_email must be a valid email address."
  }
}

variable "apim_publisher_name" {
  description = "(Optional) Publisher name shown by API Management. Defaults to Governed AI Gateways Workshop."
  type        = string
  default     = "Governed AI Gateways Workshop"
  nullable    = false
}

variable "apim_sku_name" {
  description = "(Optional) API Management SKU and capacity. It must be a v2 tier, because the Foundry AI Gateway integration only accepts v2 instances and v2 tiers provision in minutes. Defaults to BasicV2_1. See https://learn.microsoft.com/azure/api-management/v2-service-tiers-overview."
  type        = string
  default     = "BasicV2_1"
  nullable    = false

  validation {
    condition     = can(regex("^(BasicV2|StandardV2|PremiumV2)_[1-9][0-9]?$", var.apim_sku_name))
    error_message = "The apim_sku_name must be a v2 tier with capacity, for example BasicV2_1 or StandardV2_1."
  }
}

variable "apim_token_limit_enabled" {
  description = "(Optional) Whether the llm-token-limit policy is applied to every product. The workshop enables it in lab 2 with 'azd env set APIM_TOKEN_LIMIT_ENABLED true'. Defaults to false."
  type        = bool
  default     = false
  nullable    = false
}

variable "apim_content_safety_enabled" {
  description = "(Optional) Whether the llm-content-safety policy checks every prompt with Azure AI Content Safety and Prompt Shields. The workshop enables it in lab 2 with 'azd env set APIM_CONTENT_SAFETY_ENABLED true'. Defaults to false."
  type        = bool
  default     = false
  nullable    = false
}

variable "apim_content_safety_thresholds" {
  description = "(Optional) Blocking threshold per harm category for the llm-content-safety policy, using eight severity levels: 0 is the most restrictive and 7 the least. Defaults to 4 for every category. See https://learn.microsoft.com/azure/api-management/llm-content-safety-policy."
  type        = map(number)
  default = {
    Hate     = 4
    SelfHarm = 4
    Sexual   = 4
    Violence = 4
  }
  nullable = false

  validation {
    condition     = alltrue([for name in keys(var.apim_content_safety_thresholds) : contains(["Hate", "SelfHarm", "Sexual", "Violence"], name)])
    error_message = "The apim_content_safety_thresholds keys must be Hate, SelfHarm, Sexual or Violence."
  }

  validation {
    condition     = alltrue([for threshold in values(var.apim_content_safety_thresholds) : threshold >= 0 && threshold <= 7])
    error_message = "Every content safety threshold must be between 0 and 7."
  }
}

variable "apim_products" {
  description = "(Optional) API Management products, one per consumer tier. Each product gets one subscription and its own llm-token-limit values. The key becomes the product ID. Defaults to a basic tier that hits its limits quickly and a premium tier with ample capacity."
  type = map(object({
    display_name       = string
    description        = string
    tokens_per_minute  = number
    token_quota        = number
    token_quota_period = string
  }))
  default = {
    basico = {
      display_name       = "Básico"
      description        = "Consumers with a low token budget per minute and per day."
      tokens_per_minute  = 1000
      token_quota        = 5000
      token_quota_period = "Daily"
    }
    premium = {
      display_name       = "Premium"
      description        = "Consumers with a generous token budget for production workloads."
      tokens_per_minute  = 20000
      token_quota        = 1000000
      token_quota_period = "Daily"
    }
  }
  nullable = false

  validation {
    condition     = alltrue([for id in keys(var.apim_products) : can(regex("^[a-z][a-z0-9-]{1,79}$", id))])
    error_message = "Each apim_products key must start with a lowercase letter and contain only lowercase letters, digits or hyphens."
  }

  validation {
    condition     = alltrue([for product in values(var.apim_products) : contains(["Hourly", "Daily", "Weekly", "Monthly", "Yearly"], product.token_quota_period)])
    error_message = "Each token_quota_period must be Hourly, Daily, Weekly, Monthly or Yearly."
  }

  validation {
    condition     = alltrue([for product in values(var.apim_products) : product.tokens_per_minute > 0 && product.token_quota > 0])
    error_message = "Each product needs a positive tokens_per_minute and token_quota."
  }
}
