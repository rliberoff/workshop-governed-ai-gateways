# Changelog

All notable changes to this project are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Workshop "De modelos a IA gobernada: AI Gateways con Azure API Management, Microsoft Foundry y Databricks": 180-minute introductory agenda, preparation guide, concepts module, six lab guides, integrated architecture and instructor guide, in Spanish.
- Terraform `backend` layer with remote state storage that disables shared keys and grants the caller blob data access.
- Terraform `resources` layer with two Microsoft Foundry accounts (each with a project and a `gpt-6-luna` deployment), Azure AI Content Safety, API Management Basic v2 as AI gateway, Log Analytics and Application Insights.
- API Management OpenAI v1 API with managed identity authentication to Foundry, retry and circuit breaker, products and subscriptions, `llm-token-limit` and `llm-content-safety` policies toggled from the azd environment, and the built-in `llm-emit-token-metric` policy, with Application Insights custom metrics with dimensions enabled as code.
- Optional Terraform `databricks` layer with a Premium workspace, Access Connector, Unity Catalog service credential and a Unity Gateway model provider service with per-user token limits and an inference table.
- Lab 3 on the Foundry AI Gateway in its two modes: standalone, on a second Foundry account for which Foundry creates its own API Management instance, and integrated with the API Management instance of the workshop. Both are enabled in the Foundry portal, the only documented way; the lab script discovers what Foundry created through ARM resource links and the API Management management API.
- Python lab scripts for direct consumption, governed consumption, the Foundry AI Gateway, OpenTelemetry tracing and KQL queries, AI red teaming, cloud evaluations and Unity Gateway, managed with uv.

### Changed

- `AGENTS.md`, `apm.yml` and `azure.yaml` now describe this workshop instead of the template project.
