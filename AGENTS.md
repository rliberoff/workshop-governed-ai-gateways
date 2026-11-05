# Agent instructions

Guidance for any AI coding assistant working in this repository, like for example GitHub Copilot or Claude Code

This file is a router, not a second rulebook.

## Order of precedence

Apply the first source that resolves the question, and never silently override a higher one.

| Priority | Source | What it governs |
| :--- | :--- | :--- |
| 1 | A direct, explicit user directive | Overrides everything below, by rule 1 of the Copilot instructions |
| 3 | [`.github/copilot-instructions.md`](.github/copilot-instructions.md) | Interaction style, language policy, code generation and modification philosophy |
| 4 | [`.github/instructions/`](.github/instructions/) | When available, provides scoped rules, applied according to their `applyTo` glob |
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
| [`docs/`](docs/) | Workshop material in Spanish: preparation, concepts, lab guides, integrated architecture and instructor guide |
| [`inf/`](inf/) | Terraform IaC roots: `backend/` creates the state foundation; `resources/` creates the governed AI gateway with per-environment remote state; `databricks/` optionally adds Azure Databricks with Unity Gateway |
| [`src/workshop/`](src/workshop/) | Python lab scripts, KQL queries and evaluation data, managed with `uv` from the root [`pyproject.toml`](pyproject.toml) and [`uv.lock`](uv.lock) |

## Infrastructure as Code — Terraform

The workshop has three Terraform roots: `backend` creates the remote-state foundation, `resources` creates the governed AI gateway resources, and the optional `databricks` root adds Azure Databricks with Unity Gateway in front of the same Foundry deployment. Both `resources` and `databricks` use per-environment remote state. Follow the Terraform source and `azure.yaml` to determine what `azd` will provision.

No resource is created or modified from the Azure portal. The only exception, decided by the repository
owner, is lab 3: enabling the Foundry AI Gateway on a Foundry account is documented only in the Foundry
portal, so attendees associate it there, standalone on the second Foundry account and integrated with the
Terraform API Management instance. Terraform never declares the objects that Foundry creates, and code never
changes them. Manual Terraform runs use local,
unversioned `terraform.tfvars`; `azd` supplies environment-specific values from the selected local
`.azure/` environment. Neither source of environment configuration belongs in Git.

The deployment grants every managed identity its data roles and grants the deployer the data-plane
roles the labs need (Foundry User, Log Analytics Reader, Monitoring Metrics Publisher). Contributor
alone is not enough, because it cannot assign roles. Role assignments use built-in role definition IDs,
because Foundry roles were renamed recently.

### Structure

| Folder | Purpose |
| :--- | :--- |
| `backend/` | **Stage 1**. Creates the Terraform remote state resource group, storage account without shared keys, private blob container, and caller-scoped blob data role assignment. Its state is local and **must not** be committed. |
| `resources/` | **Stage 2**. Creates the governed AI gateway resources using per-environment remote state. |
| `databricks/` | **Optional stage 3**. Creates a Premium Databricks workspace, an Access Connector and the Unity Catalog objects of Unity Gateway, using per-environment remote state. |

### Modules

Each module owns its resource, its diagnostic settings and the role assignments of its identity. Module folders use the Azure abbreviation of their main resource.

| Root | Module | Resource |
| :--- | :--- | :--- |
| `resources` | `log` | Log Analytics workspace shared by gateway logs and Application Insights |
| `resources` | `appi` | Workspace-based Application Insights with local authentication disabled |
| `resources` | `aif` | Foundry account (`AIServices`) with project, model deployment and Application Insights connections; instantiated twice, for the main account and for the standalone AI Gateway account of lab 3 |
| `resources` | `cs` | Azure AI Content Safety account used by the `llm-content-safety` policy |
| `resources` | `apim` | API Management v2 instance with the OpenAI v1 API, backends, policies, products, subscriptions and logging |
| `databricks` | `dbw` | Databricks workspace, Access Connector and its role on the Foundry account |

### Tagging

All resources carry the tags from `local.tags`: `createdWith`, `createdAt`, `project`, `environment` and `owner`.

`createdAt` is recalculated on every run by design. That is why every tagged resource declares
`lifecycle { ignore_changes = [tags] }`: without it, every `plan` would propose unrelated changes.

### Technology versions

| Component | Version | Why |
| :--- | :--- | :--- |
| Terraform | `>= 1.16.5` | Every Terraform root declares this minimum |
| `azurerm` | `~> 5.9.0` | Every Terraform root uses this constraint |
| `azapi` | `~> 2.13.0` | The `resources` root uses it for properties that `azurerm` does not expose; every use is commented |
| `databricks` | `~> 1.137.0` | The `databricks` root uses this verified partner provider for Unity Catalog and Unity Gateway objects |
| Python | `>= 3.11, < 3.14` | PyRIT, used by the AI Red Teaming Agent, does not support Python 3.14 |

A provider is declared only when something consumes it, never “just in case”.

## Prerequisites

| Requirement | Check |
| :--- | :--- |
| Terraform 1.16.5 or later | `terraform version` |
| Azure CLI 2.91.0 or later, authenticated to the target subscription | `az account show` |
| Azure Developer CLI 1.36.0 or later | `azd version` |
| Python 3.11 to 3.13 and uv 0.10 or later, for the lab scripts | `uv --version` |

## Local provisioning with `azd`

`azd` runs locally on the developer workstation but provisions resources in Azure. Local provisioning is limited to the caller's isolated environment; it must not target shared, client, or PRO environments.

The root [`azure.yaml`](azure.yaml) selects Terraform and defines three provisioning layers: `backend` (`./inf/backend`), `resources` (`./inf/resources`), which depends on `backend`, and the optional `databricks` (`./inf/databricks`), which depends on `resources`. `azd provision` orchestrates the Terraform roots. It can target a layer by name; without a layer name, it provisions all configured layers in dependency order, including the optional one, so the workshop always names the layer. The [`provider.conf.json`](inf/resources/provider.conf.json) of the `resources` and `databricks` layers uses the backend layer's outputs and `AZURE_ENV_NAME` to configure their remote state. Each layer's `main.tfvars.json` maps azd environment values to Terraform variables, and UPPER_CASE Terraform outputs become azd environment values; no output carries a secret.

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
