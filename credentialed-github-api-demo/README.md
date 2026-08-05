# Credentialed GitHub API Demo

This is a minimal conformance plugin for SPRK's host-rendered configuration and secure connector foundation. It declares one optional configuration surface for the plugin and exposes exactly one approved credentialed operation:

- `GET https://api.github.com/user/repos`

The configuration is rendered by SPRK in one company-scoped plugin drawer. It includes an ordinary non-secret `Connection label` field and a connection section that references the secure connector. The label is stored separately for each company. It is not sent to GitHub and must not contain a credential.

SPRK collects the token through the connection section, encrypts it, injects it into the approved `Authorization` header, executes the request outside plugin code, and persists only the validated safe output. The operation has explicit attempt/total timeouts and bounded retries for declared transient failures. The plugin package and publisher cannot read the token.

## Install and run

1. Install `credentialed-github-api-demo.zip` from **Settings > Plugins**.
2. Make the installed package available, but leave it inactive for the selected company while completing setup.
3. Open **Configure** on the plugin.
4. Optionally enter a non-secret **Connection label** for the selected company.
5. Click **Enter GitHub token** and provide a GitHub fine-grained personal access token.
6. Click **Fetch repositories**.
7. Enable the configured plugin for the selected company when setup is complete.

The credential field is write-only and is not part of the configuration values payload. SPRK will not display the stored value after it is saved.

For public repositories, use a fine-grained token with minimal repository metadata access. Grant additional repository access only if you intentionally want private repositories included in the demo result.

## Safe output

The GitHub repository array is reduced into the connector foundation's required `accounts[]` shape:

- repository `id` becomes `externalAccountId`;
- repository `full_name` becomes `displayName`;
- repository owner, visibility, and language become optional safe metadata.

No raw GitHub response, token, request headers, mapping, import, synchronization, job, schedule, or accounting action is exposed or created.

## Configuration contract demonstrated

- The plugin declares exactly one `plugin_configuration` extension with one company-scoped `configuration` resource.
- SPRK owns and renders the configuration drawer; the bundle contains no executable UI code.
- Ordinary fields contain non-secret company values only.
- The configuration's `configure_credentials` action references the connector's `github-token` auth method. The token remains in SPRK's credential vault and is never returned as a configuration value.
- The `discover_connection` action references the exact `fetch-repositories` operation. It cannot execute another URL or undeclared request.
- `allowMultiple` is false, so this demo expects at most one GitHub authorization for each company.
- The package defines no binding section because it does not map provider data into SPRK master data.

## Runtime support

Secure connections are supported only by the embedded SPRK desktop runtime on macOS and Windows. Linux, Container, and shared-backend modes fail closed for this plugin while ordinary SPRK functionality remains available.
