# Agent instructions

Guidance for any AI coding assistant working in this repository, like for example GitHub Copilot or Claude Code

This file is a router, not a second rulebook.

## Order of precedence

Apply the first source that resolves the question, and never silently override a higher one.

| Priority | Source | What it governs |
| :--- | :--- | :--- |
| 1 | A direct, explicit user directive | Overrides everything below, by rule 1 of the Copilot instructions |
| 3 | [`.github/copilot-instructions.md`](.github/copilot-instructions.md) | Interaction style, language policy, code generation and modification philosophy |
| 4 | [`.github/instructions/`](.github/instructions/) | Scoped rules, applied according to their `applyTo` glob |
| 5 | `.agents/skills/<skill_name>/SKILL.md` | Domain conventions, applied when the skill description matches the task |
| 6 | This file | Orientation and repository facts only |

If two applicable sources conflict, or one cannot be loaded, stop the affected work and ask the user to resolve it

## Repository map

| Path | Contents |
| :--- | :--- |
| `.agents/skills/` | Skills installed by APM (Agent Package Manager) for assistants to load. Generated, do not hand-edit |
| [`.apm/skills/`](.apm/skills/) | Skills authored in this repository. Edit them here |
| [`.github/`](.github/) | GitHub repository-specific configurations, Copilot instructions, scoped instruction files, custom agents, skills and more |
| `apm_modules/` | APM package cache. Ignored by Git |
| [`inf/`](inf/) | Terraform IaC roots for the developer DEV bootstrap: `backend/` creates the state foundation; `resources/` creates the project resource group with per-environment remote state |

## Infrastructure as Code — Terraform

The current bootstrap has two Terraform roots: `backend` creates the remote-state foundation, and `resources` creates the project's resources using per-environment remote state. Follow the Terraform source and `azure.yaml` to determine what `azd` will provision; do not mistake the target solution architecture below for resources already deployed by this bootstrap.

No resource is created or modified from the Azure portal. Manual Terraform runs use local,
unversioned `terraform.tfvars`; `azd` supplies environment-specific values from the selected local
`.azure/` environment. Neither source of environment configuration belongs in Git.

The target solution deployment must also grant the solution identity its data roles and grant the
deployer the data-plane permissions needed to write secrets and configuration keys. Contributor
alone is not enough, because it cannot assign roles.

### Structure

| Folder | Purpose |
| :--- | :--- |
| `backend/` | **Stage 1**. Creates the Terraform remote state resource group, storage account, private blob container, and caller-scoped blob data role assignment. Its state is local and **must not** be committed. |
| `resources/` | **Stage 2**. Creates the project's resources using per-environment remote state. |

### Target solution modules

The target solution architecture assigns each module its resource, diagnostic settings against the shared workspace, and required role assignments. These modules and their planned providers are not present in the current bootstrap; check the constraints in each Terraform root before changing providers.

| Module | Resource |
| :--- | :--- |
| `mi` | User-assigned managed identity |
| `log` | Log Analytics Workspace |
| `appi` | Application Insights |
| `kv` | Key Vault with RBAC authorization |
| `appcs` | App Configuration |
| `st` | Storage account |
| `acr` | Container Registry |
| `ais` | `AIServices` account with project, model deployment, and content filtering policy corresponding to a Microsoft Foundry tools (milto-service account) instance |
| `app` | A web application hosting both the frontend and backend components of the solution |
| `asp` | The App Service Plan for hosting the web application |
| `srch` | Azure AI Search (a.k.a. Foundry IQ) |
| `vnet` | Virtual network |
| `snet` | Subnet within the virtual network |
| `nsg` | Network security group |
| `dns` | DNS (private) zone |
| `pep` | Private endpoint within the virtual network |
| `di` | Document Intelligence |

### Tagging

All resources carry the tags from `local.tags`: `createdWith`, `createdAt`, `project`, and `environment`.

`createdAt` is recalculated on every run by design. That is why every tagged resource declares
`lifecycle { ignore_changes = [tags] }`: without it, every `plan` would propose unrelated changes.

### Technology versions

| Component | Version | Why |
| :--- | :--- | :--- |
| Terraform | `>= 1.16.5` | Both current Terraform roots declare this minimum |
| `azurerm` | `~> 5.9.0` | The backend root uses this constraint; check the resources root for its exact pin |
| `azuread` | `~> 3.10.0` | Planned for app registrations and Graph role assignment |
| `azapi` | `~> 2.13.0` | Planned fallback for resources not supported directly by `azurerm` |
| `random` | `~> 3.9.1` | Planned stable identifier for the API scope |

A provider is declared only when something consumes it, never “just in case”.

## Prerequisites

| Requirement | Check |
| :--- | :--- |
| Terraform 1.16.5 or later | `terraform version` |
| Azure CLI 2.91.0 or later, authenticated to the target subscription | `az account show` |
| Azure Developer CLI 1.36.0 or later | `azd version` |

## Local provisioning with `azd`

`azd` runs locally on the developer workstation but provisions resources in Azure. Local provisioning is limited to the caller's isolated environment; it must not target shared, client, or PRO environments.

The root [`azure.yaml`](azure.yaml) selects Terraform and defines two provisioning layers: `backend` (`./inf/backend`) followed by `resources` (`./inf/resources`), which depends on `backend`. `azd provision` orchestrates the Terraform roots. It can target a layer by name; without a layer name, it provisions all configured layers in dependency order. The `resources` layer's [`provider.conf.json`](inf/resources/provider.conf.json) uses the backend layer's outputs and `AZURE_ENV_NAME` to configure its remote state.

Before using `azd`, verify its version and authenticate Terraform through Azure CLI. Terraform's Azure provider uses the Azure CLI identity; `azd auth login` alone does not authenticate Terraform.

```powershell
$tenantId = Read-Host "Tenant ID"
$subscriptionId = Read-Host "Subscription ID"
$environmentId = Read-Host "Unique environment ID (2-10 lowercase letters or digits)"
azd version
azd config set auth.useAzCliAuth true
az login --tenant $tenantId
az account set --subscription $subscriptionId
az account show --query "{tenantId:tenantId,id:id}" --output json
```

Use the same tenant, subscription, and developer environment ID as the Terraform bootstrap. The environment ID must be unique per developer in the shared subscription and contain 2-10 lowercase letters or digits. Create the `azd` environment once, or select it if it already exists, then set its subscription and region:

```powershell
azd env new $environmentId
azd env set AZURE_SUBSCRIPTION_ID $subscriptionId
azd env set AZURE_LOCATION swedencentral
```

The `swedencentral` location is an example of an Azure region where resources can be provisioned. You may choose a different region if required, but ensure consistency across your environment.

For an existing environment, run `azd env select $environmentId` instead of `azd env new`. `AZURE_ENV_NAME` comes from the `azd` environment name and is passed to Terraform as `environment_id`. The local environment files live under `.azure/` and are ignored by Git; treat them as local state and do not commit them or expose their values.

Review the Terraform changes before provisioning. Run `azd provision --preview` for all layers or include a layer name, such as `azd provision backend --preview`. Only after confirming the preview matches the intended isolated DEV changes, run the corresponding `azd provision` command. Keep both layers on the same authenticated Entra identity. If remote-state initialization fails with 401/403, allow up to 10 minutes for the blob data role assignment to propagate, refresh the Azure CLI session, then preview again before retrying provisioning. Do not enable shared keys or create a manual role assignment as a workaround.

For current CLI behavior, see Microsoft's guides for [Terraform with azd](https://learn.microsoft.com/azure/developer/azure-developer-cli/use-terraform-for-azd), [layered provisioning](https://learn.microsoft.com/azure/developer/azure-developer-cli/layered-provisioning), [azd environments](https://learn.microsoft.com/azure/developer/azure-developer-cli/work-with-environments), and [environment variables](https://learn.microsoft.com/azure/developer/azure-developer-cli/manage-environment-variables).

## Rules that apply to every change

- Ask before you build. [`wow-follow-up-question.instructions.md`](.github/instructions/wow-follow-up-question.instructions.md) requires at least 95% confidence before making changes, and requires you to state your confidence percentage in every exchange.
- Never emit placeholders. [`wow-no-dummy-no-placholder-code.instructions.md`](.github/instructions/wow-no-dummy-no-placholder-code.instructions.md) forbids `TODO` markers, pseudo-code markers, dummy defaults and non-functional stubs. Use real values, or the idiomatic parametric form for the language.
- Change the minimum. Preserve existing structure, style and logic; extend rather than replace; do not refactor or reformat code the request did not target.
- Declare intent before each tool call, in one concise sentence.
- Verify version-dependent facts with the `microsoft-learn` MCP server or the `microsoft-docs` skill instead of relying on model knowledge.

## Language policy

- Code, Infrastructure as Code (IaC), scripts, executable configuration, identifiers and every code comment are always in English. This includes Terraform descriptions and validation messages, XML documentation comments, log and event names, and exception messages.
- Instruction files, prompt files, custom agents and skills are always in English.
- Standalone documentation may be Spanish or English according to its audience.
- Reply to the user in the language the user writes in.
- User interface in the frontend must be in Spanish.

## Commits and pull requests

- Update the `CHANGELOG.md` with a summary of the changes made before creating a pull request. If in doubt, ask the human for guidance on how to document the change, including the version number or date.
- Every commit message and pull request title, always and without exception, follows the [`wow-conventional-commits`](.agents/skills/wow-conventional-commits/SKILL.md) skill. Load the skill before you write the message and take the format from it; never improvise one, and never take it from this file.
- The integration branch is `dev`. Work on a topic branch named after the pattern already used in the remote, `@<user>/<topic>`.
- One commit is one logical change.
- All integration happens through pull requests in Azure Repos. Direct commits to the integration branch and self-merges are prohibited.
- Attach the evidence the constitution requires when the change touches security, tests, coverage, performance or observability.

## Things not to do

- Do not commit Terraform state files, `.terraform/` directories or any `terraform.tfvars` holding environment values.
- Do not add a Terraform provider that no resource consumes, or one from an unverified publisher.
- Do not put a secret, token or personally identifiable information in code, configuration, logs or telemetry.
- Do not propose an architecture that replaces either Azure path or introduces a non-Azure runtime; that requires a constitution amendment first.
- Do not expand the scope to the iPad client, offline operation or on-device models. They are explicitly out of scope.
- Do not claim a validation ran when it did not.
