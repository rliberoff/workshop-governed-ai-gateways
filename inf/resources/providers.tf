terraform {
  required_version = ">= 1.16.5"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.9.0"
    }

    # azapi covers API Management and Foundry properties that azurerm does not expose yet:
    # managed identity credentials on backends, LLM message logging and project-level connections.
    azapi = {
      source  = "azure/azapi"
      version = "~> 2.13.0"
    }
  }

  # Partial configuration: azd fills it from provider.conf.json with the outputs of the backend layer.
  backend "azurerm" {}
}

provider "azurerm" {
  features {
    api_management {
      # Workshop environments are recreated often; a soft-deleted instance would block a new one with the same name.
      purge_soft_delete_on_destroy = true
      recover_soft_deleted         = true
    }

    cognitive_account {
      # Soft-deleted Foundry and Content Safety accounts keep their custom subdomain reserved until purged.
      purge_soft_delete_on_destroy = true
    }

    log_analytics_workspace {
      permanently_delete_on_destroy = true
    }

    resource_group {
      # In lab 3 the Foundry portal creates an API Management instance for the standalone AI Gateway. It is not
      # in the Terraform state, so 'azd down resources' could not delete this dedicated workshop resource group.
      prevent_deletion_if_contains_resources = false
    }
  }

  subscription_id = var.subscription_id
}

provider "azapi" {
  subscription_id = var.subscription_id
}
