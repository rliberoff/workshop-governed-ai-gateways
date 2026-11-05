terraform {
  required_version = ">= 1.16.5"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.9.0"
    }

    # Verified partner provider, required to manage Unity Catalog and Unity Gateway objects.
    databricks = {
      source  = "databricks/databricks"
      version = "~> 1.137.0"
    }

    random = {
      source  = "hashicorp/random"
      version = "~> 3.9.1"
    }
  }

  # Partial configuration: azd fills it from provider.conf.json with the outputs of the backend layer.
  backend "azurerm" {}
}

provider "azurerm" {
  features {
    databricks_workspace {
      force_delete = true
    }
  }

  subscription_id = var.subscription_id
}

# Workspace-level provider authenticated with the same Azure CLI identity that runs Terraform. That identity
# becomes workspace admin on first access, and on workspaces with automatic Unity Catalog enablement workspace
# admins can create service credentials.
provider "databricks" {
  host                        = module.dbw.workspace_url
  azure_workspace_resource_id = module.dbw.workspace_id
  auth_type                   = "azure-cli"
}
