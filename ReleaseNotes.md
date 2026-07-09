# Release Notes — Upwind Catalog Loader

## v1.1.0

### Features
- **Expanded from 1 to 6 Upwind API endpoints**: inventory/catalog assets (now all categories, not just compute platform), vulnerability findings, threat detections, threat events, threat stories, and configuration (posture) findings — each ingested to its own custom Log Analytics table via its own DCR stream
- Each dataset is fetched and uploaded independently per run; one Upwind endpoint failing (e.g. not entitled for a given org) no longer blocks the others
- New pagination strategies to match each endpoint: page-number pagination (threat detections/events), HTTP `Link`-header pagination (vulnerability findings), and time-windowed POST+cursor pagination (threat stories, configuration findings), alongside the existing cursor-based pagination for inventory assets
- New `UpwindThreatLookbackMinutes` parameter controls the time window for the four time-windowed datasets (default 90 minutes)

### Fixes
- **Support Log Analytics workspace in a different resource group** (`WorkspaceResourceGroup` parameter) — the ARM template previously assumed the workspace lived in the same resource group as the deployment, causing `workspaces/tables` write failures for anyone with a separate resource group per workspace
- **Fix Linux Function App deployment failure** (`"The parameter LinuxFxVersion has an invalid value"`) — the App Service Plan was missing `"reserved": true`, so it provisioned as Windows despite the site being configured for Linux; this also silently blocked every other resource in the template from being created, since ARM validates the whole template before creating anything
- **Rename reserved/invalid column names** — `title` and `type` are rejected by the Log Analytics custom table schema API; renamed to `title_text` and `event_type` in the four affected tables (threat detections, threat events, threat stories, configuration findings)

## v1.0.0 (Initial Release)

### Features
- Azure Function (Python 3.11, timer trigger) that ingests compute platform assets from the Upwind cloud security platform
- OAuth2 client_credentials authentication against `https://auth.upwind.io/oauth/token`
- Paginated POST to Upwind `/v2/organizations/{orgId}/inventory/catalog/assets/search` with `compute_platform` category filter
- Cursor-based pagination with exponential backoff on 429 / transient errors
- Sends asset records to a custom Log Analytics table (`UpwindCatalogAssets_CL`) via the Azure Monitor Ingestion API (DCE + DCR)
- Single ARM template deploys all required Azure resources: DCE, custom table, DCR, role assignment, App Service Plan, storage, Application Insights, and Function App
- Configurable timer schedule (default: top of every hour)
