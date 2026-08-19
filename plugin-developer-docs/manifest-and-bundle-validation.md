# Manifest and Bundle Validation

SPRK validates the root manifest, every extension manifest, and all references
between them before installation or enablement.

## Root-manifest rules

- `schemaVersion` must be `"2"`; required root fields must be non-empty.
- `internetAccess.required: true` requires a non-empty `reason`.
- `api.execute.methods` may contain only `GET`, `POST`, `PUT`, `PATCH`, and
  `DELETE`, with no duplicates. It needs at least one method when required.
- `plugin.bindings.manage.targets` may contain only `accounts`, `customers`,
  `items`, and `vendors`.
- `actions.run` supports only `manual`; when required, its allowed triggers
  must include `manual`.
- `data.sprk` permits only `accounts`, `customers`, `items`, and `vendors`,
  with `list`, `get`, and `resolve` operations.
- `review.imports` supports `bank_register`, `accounts`, `customers`, `vendors`,
  and `items`.
- `review.proposals` contains exact native or plugin-resource target grants.
  Native combinations are accounts/vendors/items create, customers
  create-or-link, and invoices create-draft.
- `surfaces.contribute.surfaces` supports `banking.import.source.actions`,
  `chart`, `customers`, `vendors`, `items`, `reports.catalog.entries`, and
  `plugin_pages.header.actions`.
- `reports.query.sources` is a non-empty exact source ID/version allowlist when
  required. Current source IDs are `gl.lines`, `invoice.lines`, and
  `bank.register`, all at version `1`.
- `workflows.run`, `records.query`, `records.write`, and
  `accounting.journal.propose` are strict `{required}` grants. They do not
  authorize direct native/core writes.
- Extension reference IDs must be unique.

## Extension rules

- The extension envelope must be valid and its type must be supported.
- Resource IDs must be unique within an extension. Every resource has
  `schemaVersion: 1` and `scope: "company"`.
- A `records` resource needs a record schema unless it is part of a `new_page`
  extension. Record schemas contain 1–128 uniquely named fields.
- A connector needs exactly one connector resource, is company-scoped, and
  cannot request direct secret access.
- A configuration extension needs exactly one configuration resource, is
  company-scoped, and cannot request direct secret or network access.
- An existing-page-actions extension has at least one `run_action`; each needs
  an `action` reference to a declared manual action.
- A new report may set `definitionVersion: "2"` and retains `report`, `data`,
  `views`, and optional `customization`. It needs exactly one granted semantic
  source, explicit basis metadata, and at least one table view.
- A new workflow uses `definitionVersion: 1`, manual trigger only, 1–32
  workflows, at most 32 typed inputs, and 1–16 top-level commands.

## Cross-extension rules

- A bundle may declare at most one configuration extension.
- API and connector operations must use HTTP methods granted by
  `capabilities.api.execute.methods`.
- Connector pagination needs a referenced `host_only` records resource with a
  required string `cursor` field.
- Actions need the manual `actions.run` grant. Their data, API, review,
  binding, and resource steps each need the matching declared capability and
  resource. A review-import step is terminal. `bank_register` requires
  `target.accountId: "$context.targetId"`; master-data targets require an empty
  `target`. Fields, types, and required mappings must match the selected native
  import schema.
- `fieldMappings` is optional unless referenced by terminal `review.propose`.
  Mapping IDs are unique; every mapping has an authorized source, exact granted
  target, non-empty typed field map, and valid source/target fields. Plugin-page
  actions must read from or write to that page's records resource.
- Plugin-resource snapshot sync requires `full_snapshot`, a stable identity,
  `mark_inactive`, and a Boolean inactive field. It never authorizes deletion.
- Configuration references must point to an existing connector extension and
  connector resource. Configuration values used by an action must be declared.
- Every existing-page action needs the surface grant matching its
  `targetPageKey`. A `run_action` target must be an existing manual action.
- A bank review action must use the accounts-to-accounts binding that supplies
  its selected Banking target and connection. A master-data page-header review
  must omit `action.binding` so the host can select a connected company
  connection for the action's connector. The review target must match the
  contributed page surface.
- Every `api.execute` step in one action must use the same connector resource;
  one action run has one host-selected connection context.
- Every report source/version must match `reports.query`; a report entry also
  needs `reports.catalog.entries` in `surfaces.contribute`.
- Query fields, operators, measures, groups, sorts, basis, date field, posting
  state, and amount mode must be supported by the resolved source catalog.
- A manual workflow targets a same-plugin resource-backed `new_page` with a
  user-accessible records resource and the `plugin_pages.header.actions`
  surface grant. Plugin-resource queries are restricted to that target.
- Workflow input defaults must match their declared rich types. Native
  references require exact data grants; plugin references require
  `records.query` and a user-accessible same-plugin records resource.
- Workflow command IDs are globally unique, sources refer only to optional
  selection, `$item` in a for-each calculation, or an earlier list result.
  Branches are data-only; stop and journal preview are terminal in their
  blocks; journal preview requires one earlier review and its proposal grant.

## Bounds and compatibility

Actions have 1–32 actions per extension and 1–16 steps per action. New-plugin
authoring uses `connector` plus `api.execute`; compatibility-only direct API
extensions and page actions are excluded from the normative schema.

Workflows have at most 16 commands per block, 128 commands across the graph,
branch depth 3, expression depth 6, predicate depth 3, and 500 records per
collection. Sort has at most 4 keys, distinct 8 fields, aggregate 8 group fields
and 16 measures, and join 4 key pairs with a unique right side and 500-row output.

New bundles must declare `api.execute` with the smallest method set for every
external operation.

Report queries never contain SQL, table names, joins, subqueries, or arbitrary
expressions. Runtime limits include 20 columns, 20 filters, 3 group levels,
predicate depth 4, and page size 500. Runtime budgets and errors are listed
in [Native Custom Reports](native-custom-reports.md).

The install preview reports invalid root manifest, incompatible runtime,
invalid extension set, invalid extension manifest, and invalid bundle-contract
errors. Correct all errors before installation or enablement.
