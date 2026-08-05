# On-Demand Weather Plugin

Demo plugin for the manual `api_calls` connector path.

Zip this directory with `manifest.json` at the archive root and install it once from Settings > Plugins. Enable it explicitly for the company where it should run, launch the backend with `SPRK_ENABLE_PLUGIN_API_CALLS=true`, then open Banking and click `Pull Demo Data`.

The runtime snapshot is company-scoped at `GET /v1/companies/:companyId/plugin-runtime/snapshot`. The action executes through `POST /v1/companies/:companyId/plugins/demo-on-demand-weather/extensions/demo-weather-api/api-calls/current-weather/execute` with the current snapshot ID in `If-Match`. Installation is app-wide; activation and execution are company-specific.
