# Security and Data Boundaries

SPRK plugins are declarative packages. The host renders UI, stores plugin-owned
records, owns credentials, executes approved HTTPS operations, validates native
workflows, and preserves audit behavior. A bundle is data, not executable code.

## Trust boundaries

| Boundary | Plugin may declare | Plugin may not do |
| --- | --- | --- |
| Bundle | Manifests, resources, fields, operations, actions, and presentation metadata | Ship or execute arbitrary frontend, backend, browser, shell, SQL, or transform code |
| Network | HTTPS base URLs, bounded methods, paths, variables, timeouts, retry policy, and safe outputs | Call undeclared destinations, follow a path to another host, or request unrestricted network access |
| Credentials | Credential field labels, supported auth method, and bounded injection location | Read credentials back, log them, store them in configuration, or request direct secret access |
| Provider response | Explicit safe-output paths, field types, item bounds, and discovery mapping | Persist or expose an unrestricted response body through a connector action |
| Plugin data | Company-scoped `records` resources declared in manifests | Create provider-specific core tables or use undeclared storage |
| Core SPRK data | Bounded `list`, `get`, and `resolve`; host review; canonical bindings and workflows | Directly mutate accounts, customers, vendors, items, bank records, journals, or another core record |
| Accounting | Propose schedules, mappings, imports, source documents, and postings to host workflows | Bypass double entry, permissions, locks, audit history, review, reconciliation, reversal, or void logic |

## Credentials and authorization

- Never include a token, API key, client secret, private key, password, or live
  credential in a bundle, example, screenshot, error report, or test fixture.
- Use `connector.authMethods`. Currently supported secure patterns include API
  key, client keys, OAuth 2 PKCE, and hosted token exchange, subject to each
  method's validator rules.
- Username/password credential declarations are intentionally rejected.
- The host collects credentials, encrypts or otherwise protects them through
  the host credential system, and injects them only into declared locations.
- Ordinary configuration fields are non-secret company settings. If a value
  would be harmful when read from stored configuration or logs, it does not
  belong there.
- Connector and configuration extensions cannot request direct secret access.
  Configuration extensions also cannot request direct network access.

## Network safety

- `baseUrl` must be HTTPS. Operation paths must remain on that hostname.
- Grant only the used HTTP methods in `capabilities.api.execute.methods`.
- Declare external calls through `connector`, including operations that do not
  require credentials. Do not use undeclared headers or authentication fields.
- Connector variables and credential injections are allowlisted declarations,
  not a general header-construction facility.
- Declare finite attempt and total timeouts. Retries must be bounded and limited
  to declared transient conditions.
- Treat write operations as non-idempotent unless the provider contract and the
  declared operation semantics prove retry safety.
- Pagination must declare page and item bounds and host-owned cursor state.

## Safe-output reduction

An action must convert provider output to one to eight named safe-output
collections. Each collection declares:

- a collection ID;
- the item path;
- `maxItems` between 1 and 10,000; and
- an explicit map of output field names to source paths and SPRK data types.

Only those projected fields should flow into later persistence or review steps.
Prefer smaller limits and fewer fields. Do not use descriptions, memos, or
provider payloads as a covert channel for credentials or unrelated personal
data.

## Company isolation and storage ownership

- All plugin resources are company-scoped and use resource `schemaVersion: 1`.
- `host_only` is valid only for records resources. Use it for state the host
  manages, such as a cursor, not as a shortcut around the credential vault.
- Plugin-owned IDs and resource schemas are persisted contracts. Make evolution
  additive; retain tolerant readers and migration paths for existing records.
- A plugin should not assume that installation implies activation for every
  company. Enabling, configuration, connections, and execution are company
  scoped.
- Uninstall can be blocked by live connections or protected plugin data.

## Core data and review

- Native reads require an exact entity/operation grant.
- Bindings must use the canonical binding service and a granted target type.
- Imported bank activity and supported account, customer, vendor, or item rows
  enter their owning native review through `review.import`. Provider data is
  staging evidence, not core or accounting truth merely because a provider
  supplied it.
- Core mutations must use the same schemas, validation, permissions, review
  surfaces, and audit behavior as first-party UI. If the canonical host workflow
  cannot perform the use case safely, the plugin use case is unsupported until
  the host gains a generic capability.

## Accounting boundary

The GL is the accounting source of truth. For plugin-generated accounting:

- Debits must equal credits, and posted activity must preserve the accounting
  equation.
- The plugin cannot bypass cutoff dates, hard-locked periods, reconciliation,
  control-account rules, approval, or company compliance settings.
- Posted history must remain reconstructable through audit, reversal, void,
  supersede, or additive correction. Disabling or uninstalling a plugin must not
  erase posted accounting history.
- Plugin source, version, schedule/template/rule, posting run, source record,
  and reversal relationship must remain traceable.
- Foreign-currency proposals must preserve transaction currency, source amount,
  rate or rate policy, rate date, and base-currency measurement; no hidden FX
  account or rate selection is allowed.
- Direct posting is not a safe default for imported or generated activity.
  Prefer staging and review unless a trusted host autopost policy explicitly
  permits the same guarded workflow.

## Logging and diagnostics

Errors should identify the plugin, extension, operation, and JSON path without
including credentials, authorization codes, tokens, raw secure headers, or an
unreduced provider body. A safe diagnostic explains which declaration failed
and why; it does not echo sensitive inputs.
