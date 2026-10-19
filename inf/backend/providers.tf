terraform {
  required_version = ">= 1.16.5"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.9.0"
    }
  }
}

provider "azurerm" {
  features {}

  subscription_id = var.subscription_id

  # The state storage account disables shared keys, so data-plane calls must use Microsoft Entra ID.
  storage_use_azuread = true
}
