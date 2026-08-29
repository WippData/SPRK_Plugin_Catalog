# SPRK Plugin Developer Guide

This is the normative API guide for building new SPRK Desktop declarative plugins.
Plugin bundles are ZIP archives installed through **Settings > Plugins**. The
host validates manifests, renders the supported UI, owns credentials and
plugin-owned storage, and executes approved operations. Bundles do not contain
arbitrary frontend, backend, or browser code.

The current contract is `schemaVersion: "2"`. Build new plugins only from the
extension types and shapes documented here.

## Start here

1. Use [Choose a Plugin Shape](agent-decision-guide.md) to select the smallest extension set.
2. Copy the complete example closest to the requested result: the
   [records-page starter](starter-records-page.md),
   [bank review import](examples/review-import-bank/),
   [customer review import](examples/review-import-customers/),
   [CRM conversion](examples/review-convert-crm/),
   [reviewed provider snapshot](examples/review-sync-plugin-records/),
   [manual renewal workflow](examples/workflow-renewal-review/), or a
   [native custom report](native-custom-reports.md).
3. Use the [Typed Field Reference](schema-v2-field-reference.md) for every field and nested type.
4. Attach [plugin-manifest.schema.json](plugin-manifest.schema.json) to your editor or generator.
5. Follow [Implementation Recipes](cross-extension-recipes.md) for connectors, actions, review, and storage.
6. Run `npm run validate:plugin -- path/to/plugin-folder` after every structural change.
7. Complete the [Testing and Release Checklist](testing-and-release-checklist.md), including Install Preview for the exact ZIP.

## Hard capability boundary

The documented command and extension enums are closed allowlists. Do not invent
commands or fields when a requested operation is missing. In particular, the
current action runner has no file-upload input, pasted-CSV parser, spreadsheet
parser, free-form JSON transform, validation-script step, scheduler, or
arbitrary code execution. Manual `workflow` extensions separately provide
bounded loops, branches, collection shaping, and structured expressions; see
[Manual Plugin Workflows](manual-plugin-workflows.md). `review.import` cannot read rows from
`$inputs`; its `source` must be a declared safe-output collection from an
earlier connector `api.execute` step. `review.propose` accepts either an
authorized plugin-record selection or a declared earlier safe output, and still
requires host review before a canonical write.

If the requested plugin depends on an absent primitive, report that capability
as unsupported and stop. Adding a new bounded host primitive is a separate
platform design decision, not plugin syntax.

## Bundle layout and lifecycle

Zip the bundle with `manifest.json` at the archive root:

```text
my-plugin.zip
├── manifest.json
└── extensions/
    ├── actions.json
    └── configuration.json
```

Installation is application-wide. Enabling, configuration, connections, and
execution are company-scoped. Never put secrets, private keys, or provider
tokens in a bundle: SPRK collects supported connector credentials through its
host UI and keeps them write-only in its credential vault.

The importer accepts at most 100 files, a 10 MiB compressed archive, 25 MiB
expanded contents, 5 MiB per file, and 1 MiB per manifest. Paths must be
relative, use forward slashes, and be unique. An upgrade must retain the same
`pluginId`, use a newer version, and occur while the installed plugin is
disabled.

## Root manifest syntax

Every bundle has this shape. Omit capabilities that are not required.

```json
{
  "schemaVersion": "2",
  "pluginId": "acme.inventory-sync",
  "name": "Acme Inventory Sync",
  "version": "1.0.0",
  "publisher": {
    "id": "acme",
    "name": "Acme, Inc.",
    "supportEmail": "support@example.com",
    "website": "https://example.com"
  },
  "description": "Optional short description.",
  "runtime": { "minAppVersion": "1.0.0" },
  "capabilities": {},
  "extensionManifests": [
    {
      "extensionId": "sync-actions",
      "path": "extensions/actions.json"
    }
  ]
}
```

Required fields are `schemaVersion`, `pluginId`, `name`, `version`,
`publisher.id`, `publisher.name`, and `runtime.minAppVersion`. `runtime` may
also set `maxAppVersion`. Each extension reference needs a unique
`extensionId` and a `path`; `sha256` is optional.

`pluginId`, `extensionId`, `resourceId`, field IDs, and action IDs must start
with a lowercase letter or number and otherwise contain only lowercase letters,
numbers, periods, underscores, or hyphens. Treat these IDs as persistent
contract keys, not display labels.

## Extension manifest syntax

Each referenced extension file uses this envelope:

```json
{
  "schemaVersion": "2",
  "extensionId": "sync-actions",
  "type": "actions",
  "name": "Inventory synchronization",
  "version": "1.0.0",
  "description": "Optional short description.",
  "targets": { "companyScoped": true },
  "resources": [],
  "definition": {}
}
```

`definition` is required and its exact syntax depends on `type`. The host
validates required values, references, and capability coverage.

| Type | Purpose |
| --- | --- |
| `new_page` | Host-rendered list or transaction page, with declared fields, actions, and optional plugin-owned data source. |
| `expand_page` | Adds declared fields or actions to a supported plugin page. |
| `accounting_schedule` | Host-rendered accounting schedule with declared calculation and posting configuration. |
| `report` | Host-rendered report with declared source, fields, measures, filters, and views. |
| `connector` | Secure host-executed external connection with host-owned credentials. |
| `actions` | Bounded host-executed manual action graph. |
| `workflow` | Page-bound manual collection computation and host review with bounded control flow. |
| `plugin_configuration` | The single host-rendered, company-scoped settings surface for a plugin. |
| `existing_page_actions` | A declared action on an approved existing SPRK surface. |

See the [Typed Field Reference](schema-v2-field-reference.md) for the complete
new-plugin contract and [Manifest and Bundle Validation](manifest-and-bundle-validation.md)
for the rules that determine whether a bundle is accepted.

## Capabilities

Capabilities are explicit root-manifest declarations. They inform the install
experience and grant bounded host behavior; request the smallest set needed.

| Capability key | Use it when | Allowed values / notes |
| --- | --- | --- |
| `internetAccess` | The plugin connects to an external provider. | `required` and, when true, a non-empty `reason`. This is an install disclosure; outbound HTTP is granted by `api.execute`. |
| `api.execute` | A `connector` extension or action executes HTTP. | `required` and `methods`, selected from `GET`, `POST`, `PUT`, `PATCH`, `DELETE`. Declared operations must use a granted method. |
| `plugin.bindings.manage` | An action manages a mapping to SPRK master data. | `required` and `targets`: `accounts`, `customers`, `items`, or `vendors`. |
| `actions.run` | The bundle declares an `actions` extension. | `required: true` and `allowedTriggers: ["manual"]`. Scheduled/background actions are not supported. |
| `data` | An action reads supported native SPRK data. | `required` and `sprk` grants. Entities: `accounts`, `customers`, `items`, `vendors`; operations: `list`, `get`, `resolve`. This is not a direct core-record write grant. |
| `review` | An action submits an import or record proposal for host review. | `required` and at least one of `imports` or exact `proposals` target grants. |
| `surfaces.contribute` | An extension contributes to an approved host surface. | `required` and `surfaces`; supported keys include native surfaces, `reports.catalog.entries`, and `plugin_pages.header.actions`. |
| `reports.query` | A report executes against host semantic data. | `required` and an exact `sources` allowlist of supported `sourceId`/`sourceVersion` pairs. |
| `workflows.run` | The bundle declares a manual `workflow` extension. | `{ "required": true }`. |
| `records.query` | A workflow queries a same-plugin records resource or exposes plugin-record reference options. | `{ "required": true }`; same-plugin and company scope are still enforced. |
| `records.write` | Reserved for host-supported plugin-record workflow updates. | It never grants native/core record writes. Manual workflow authoring does not currently expose `records.update`. |
| `accounting.schedules.manage` | A public v2 accounting schedule manages company schedules. | `{ "required": true }`; authorization remains company/plugin/extension scoped. |
| `accounting.journal.propose` | A workflow builds a journal preview or a public v2 accounting schedule proposes recognition journals. | `{ "required": true }`; preview, exact review, and posting remain host-owned, and the grant never permits direct GL writes. |

An `actions` extension requires `actions.run`. Individual action steps require
the matching capability: `data.*` needs `data`, `api.execute` needs
`api.execute`, `review.import` and `review.propose` need `review`, and a binding needs
`plugin.bindings.manage`. Every existing-page action requires
`surfaces.contribute` for its exact `targetPageKey`.

A new `report` extension requires `reports.query` plus
`surfaces.contribute: ["reports.catalog.entries"]`, optional
`definitionVersion: "2"`, and at least one table view. The installed
app's `GET /v1/plugin-sdk/report-sources` catalog remains authoritative: schema validity
does not guarantee a source or field is available in a particular app version
or company. See [Native Custom Reports](native-custom-reports.md).

The current runtime exposes only `gl.lines@1`, `invoice.lines@1`, and
`bank.register@1`. It does not yet expose typed parameters, field-option lookup,
plugin-report exports, charts, or pivots. Treat disabled export controls and
retained saved views as host UI state, not as additional plugin permissions.

## Manual workflows

Use `actions` for connector calls, safe outputs, imports, and reviewed record
proposals. Use `workflow` when a user launches a page-bound collection flow
that needs optional selected rows, rich host-rendered inputs, filtering,
sorting, distinct/group/aggregate/join operations, bounded branching, or
terminal record/journal review. Read [Manual Plugin Workflows](manual-plugin-workflows.md)
and start from the [renewal workflow example](examples/workflow-renewal-review/).

Workflow triggers are manual only. Selected rows are optional execution
context, not a workflow-definition field. Schedules, background execution,
arbitrary code, and direct native/accounting mutations remain unsupported.

## Resources and data ownership

Declare plugin-owned storage under `resources`:

```json
{
  "resourceId": "sync-state",
  "kind": "records",
  "schemaVersion": 1,
  "scope": "company",
  "access": "host_only",
  "recordSchema": {
    "fields": [
      { "fieldId": "cursor", "dataType": "string", "required": true }
    ]
  }
}
```

All resources are company-scoped and use resource `schemaVersion: 1`.
`records` resources are plugin-owned storage; their fields may be `string`,
`number`, `boolean`, `date`, `datetime`, or `currency`. `host_only` records
are appropriate for host-managed state, such as a connector pagination cursor.

Connector extensions declare exactly one `connector` resource and may also
declare `records` resources. A `plugin_configuration` extension declares
exactly one `configuration` resource. A bundle may contain at most one
`plugin_configuration` extension.

Do not create plugin-specific core tables or introduce private core-record
write paths. Integrations must use the same host workflows, validation, review,
permissions, audit behavior, and accounting rules as SPRK's first-party UI.

## Connections, configuration, and actions

Use `connector` for provider authentication and API operations. Connector
definitions are declarative and host-executed: they do not permit scripts,
plugin-readable secrets, arbitrary response transforms, or unrestricted
credential/header injection. Connector and configuration extensions cannot
request direct `secrets` access; configuration extensions cannot request direct
`network` access.

Use `plugin_configuration` for ordinary per-company fields, connection
sections, and bindings. Connection sections reference a connector extension and
its connector resource; SPRK provides credential configuration or authorization
through the host UI.

Use `actions` for a manual sequence. Actions have an ID, label,
`trigger: "manual"`, optional inputs/binding, optional reusable `fieldMappings`,
and bounded host steps. Prefer
`existing_page_actions` with `kind: "run_action"` to expose one on an approved
page. Keep execution in the bounded action runner.

Declare all new external HTTPS operations through `connector`, including
operations that do not require credentials.

Use [Reviewed Record Proposals](reviewed-record-proposals.md) when selected
plugin rows or normalized provider rows should become native or plugin-owned
records through the one-row drawer or multi-row import-preview workflow.

## Accounting extensions

`accounting_schedule` is accounting-impacting. The GL remains the source of
truth, debits equal credits, and posted history is preserved through audit,
reversal, void, supersede, or additive correction as appropriate. Do not create
a plugin-only accounting write path.

Public schedule definitions set `definitionVersion: "2"`, declare both
accounting capabilities, and provide typed period-count and opening-recognition
sources. They also declare a required string `sourceReference` field. Legacy
definitions that omit the version remain install-compatible but are not public
runtime pages.

Public v2 schedule pages support host-reviewed CSV and XLSX import without a
connector or file-workflow capability. The first row (and first XLSX worksheet)
uses declared schedule field IDs and account role IDs. Account values resolve
by exact company account ID first, then unique company account code, and remain
subject to active, posting, and role account-type validation. The host caps a
preview at 500 rows and requires its exact hash for an atomic draft-only commit;
`importKey` replay is idempotent. Import never posts a journal.

## Validation and references

Start from the complete example that matches the plugin shape. Run the local
validator before packaging:

```bash
npm run validate:plugin -- path/to/plugin-folder
```

Zip the bundle contents—not its parent directory—so `manifest.json` stays at
the archive root.

Before distributing a plugin, install it, review the install preview, enable it
for a test company, and exercise each declared connection, action,
configuration, and review surface. Use these companion documents:

- [Plugin Syntax Models](syntax-models.md)
- [Typed Field Reference](schema-v2-field-reference.md)
- [Machine-Readable JSON Schema](plugin-manifest.schema.json)
- [Manifest and Bundle Validation](manifest-and-bundle-validation.md)
- [Bundle Installation and Lifecycle](bundle-installation-and-lifecycle.md)
- [Choose a Plugin Shape](agent-decision-guide.md)
- [Supported Plugin Patterns](supported-plugin-patterns.md)
- [Current Starter Records Page](starter-records-page.md)
- [Implementation Recipes](cross-extension-recipes.md)
- [Native Import Reviews](native-import-reviews.md)
- [Security and Data Boundaries](security-and-data-boundaries.md)
- [Testing and Release Checklist](testing-and-release-checklist.md)
- [Troubleshooting and Errors](troubleshooting-and-errors.md)
- [API Versioning](api-versioning.md)
