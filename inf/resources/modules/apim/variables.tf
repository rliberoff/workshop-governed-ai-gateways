variable "name" {
  description = "(Required) Name of the API Management instance. It must be globally unique because it defines the gateway host name."
  type        = string
  nullable    = false
}

variable "location" {
  description = "(Required) Azure region of the API Management instance."
  type        = string
  nullable    = false
}

variable "resource_group_name" {
  description = "(Required) Name of the resource group that contains the API Management instance."
  type        = string
  nullable    = false
}

variable "subscription_id" {
  description = "(Required) Azure subscription ID, used to build built-in role definition IDs."
  type        = string
  nullable    = false
}

variable "publisher_name" {
  description = "(Required) Publisher name shown by API Management."
  type        = string
  nullable    = false
}

variable "publisher_email" {
  description = "(Required) Publisher email address of API Management."
  type        = string
  nullable    = false
}

variable "sku_name" {
  description = "(Required) API Management v2 SKU and capacity, for example BasicV2_1."
  type        = string
  nullable    = false
}

variable "api_path" {
  description = "(Required) Base path of the governed API, without leading or trailing slashes."
  type        = string
  nullable    = false
}

variable "foundry_account_id" {
  description = "(Required) Resource ID of the Foundry account the gateway calls."
  type        = string
  nullable    = false
}

variable "foundry_openai_v1_endpoint" {
  description = "(Required) Base URL of the OpenAI v1 API of the Foundry account, without a trailing slash."
  type        = string
  nullable    = false
}

variable "content_safety_id" {
  description = "(Required) Resource ID of the Azure AI Content Safety account."
  type        = string
  nullable    = false
}

variable "content_safety_endpoint" {
  description = "(Required) Endpoint of the Azure AI Content Safety account, without a trailing slash."
  type        = string
  nullable    = false
}

variable "content_safety_enabled" {
  description = "(Required) Whether the llm-content-safety policy screens prompts."
  type        = bool
  nullable    = false
}

variable "content_safety_thresholds" {
  description = "(Required) Blocking threshold per harm category, from 0 (most restrictive) to 7 (least restrictive)."
  type        = map(number)
  nullable    = false
}

variable "token_limit_enabled" {
  description = "(Required) Whether the llm-token-limit policy is applied to every product."
  type        = bool
  nullable    = false
}

variable "products" {
  description = "(Required) API Management products keyed by product ID, with their token limits."
  type = map(object({
    display_name       = string
    description        = string
    tokens_per_minute  = number
    token_quota        = number
    token_quota_period = string
  }))
  nullable = false
}

variable "log_analytics_workspace_id" {
  description = "(Required) Resource ID of the Log Analytics workspace that receives the resource logs."
  type        = string
  nullable    = false
}

variable "application_insights_id" {
  description = "(Required) Resource ID of the Application Insights component used by the gateway logger."
  type        = string
  nullable    = false
}

variable "application_insights_connection_string" {
  description = "(Required) Connection string of the Application Insights component used by the gateway logger."
  type        = string
  sensitive   = true
  nullable    = false
}

variable "tags" {
  description = "(Required) Tags assigned to the API Management instance."
  type        = map(string)
  nullable    = false
}
