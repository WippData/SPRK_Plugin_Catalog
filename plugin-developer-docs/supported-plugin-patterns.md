# Supported Plugin Patterns

New plugins should be assembled from these host-rendered building blocks.

## Use these extension types

| Extension | Use it for | Required pairing or limit |
| --- | --- | --- |
| `new_page` | Plugin-owned list or transaction records | Use a declared `records` resource and host-rendered fields/actions. |
| `connector` | External HTTPS authentication and operations | Pair with configuration; credentials remain host-owned. |
| `plugin_configuration` | Company settings, connections, and bindings | Exactly one configuration extension and resource per bundle. |
| `actions` | Bounded manual data/API/review operations | `trigger` is `manual`; declare exact capabilities. |
| `workflow` | Manual collection/review or journal-commit writeback | Manual flows target a resource-backed page; the event flow is headless/inputless and same-plugin only. |
| `existing_page_actions` | Expose an action on an approved SPRK surface | Use only `kind: "run_action"`. |
| `report` | Native table reports and company-shared saved views | Use the executable `data`/table-`views` shape, exact semantic-source grants, declared filters/groups/measures, and bounded customization flags. |
| `accounting_schedule` | Host-controlled accounting schedule proposals | Requires balanced host posting and full accounting safeguards. |
| `expand_page` | Approved additions to an existing plugin page | Confirm the target host surface before depending on it. |
| `document_template` | Trusted alternate layouts for registered native documents | Declare `documents.render`; JSON nodes are host-rendered and do not mutate or post the source record. |

## Standard authenticated integration

Use four declarations with separate responsibilities:

1. A `connector` declares authentication, exact HTTPS operations, timeouts,
   retries, variables, pagination, and narrow output projections.
2. `plugin_configuration` renders fields, connection actions, and bindings.
3. `actions` performs a bounded manual sequence using the connector.
4. `existing_page_actions` exposes the action through `run_action` on an
   approved surface.

## Standard plugin-owned page

Use one `new_page` extension with:

- a company-scoped `records` resource;
- a resource-backed page data source;
- fields whose IDs/types match the resource schema;
- host-rendered table/drawer configuration;
- only declared page and row actions.

## Standard manual collection workflow

Pair a `workflow` extension with a resource-backed `new_page`. Declare
`workflows.run`, `records.query`, and `plugin_pages.header.actions`; use rich
host-rendered inputs and optional selected rows; shape records with filter,
sort, distinct, aggregate, join, calculate, `control.if`, and
`control.switch`; end with host review when a user decision is required. See
[Manual Plugin Workflows](manual-plugin-workflows.md).

## Standard manual file workflow

Add a workflow-only `file` input plus the exact `files.ingest` CSV/XLSX grant.
The host stages a user-selected file before execution; clicking Submit remains
the manual trigger. Start the command graph with `dataset.read`, then use the
same bounded calculations, filters, branches, and review surfaces as any other
manual workflow. The plugin receives normalized typed rows, never raw bytes or
a filesystem path. See [workflow-file-review](examples/workflow-file-review/).

This does not replace `pageActions: import`. Direct CSV/XLSX import into a
plugin page's records remains available and has its existing behavior.

## Standard journal-commit writeback

Pair a reviewed manual journal-proposal workflow with a headless
`accounting.journals.committed` workflow. Grant the exact event plus
`records.write`, filter to the proposing same-plugin workflow, consume
`$event.journals`, and end with `records.update` to a user-accessible same-plugin
records resource. The host queues the event only after exact-hash canonical
commit. See [Journal-Commit Event Workflows](event-driven-workflows.md).

## Standard native document template

Use a company-scoped `document_template` extension with
`definitionVersion: 1`, a registered native source/version, and only the
bounded document nodes in the typed field reference. Grant the exact trusted
outputs through `documents.render`. SPRK resolves the record, validates every
field path against the source contract, and renders preview/PDF/print output in
the host. See the uncataloged `alternate-invoice-layout-demo` at the repository
root for a complete invoice example.

## Standard bank-import integration

Use connector safe outputs to normalize provider data, then make
`review.import` the terminal action step. Declare the accounts-to-accounts
action binding so the selected Banking candidate supplies the connection and
target account. The host stages candidates for native review and confirmation.
The plugin never writes the Bank Register or GL directly.

## Standard master-data import integration

Use connector safe outputs to normalize account, customer, vendor, or item
rows, then make `review.import` the terminal action step. Map only the canonical
keys from [Native Import Reviews](native-import-reviews.md), use an empty
`target`, omit action binding, and expose the action through
`existing_page_actions` on the owning native page. The host selects a connected
company connection for the action's connector, then opens that page's normal retryable import preview and
commits through the same core APIs as a file import. The plugin never writes a
core table directly.

## Standard reviewed conversion

Declare optional `fieldMappings` on an actions extension and end the referenced
manual action with `review.propose`. A `plugin_selection` mapping can convert a
row or explicit selection from a host-rendered plugin page into native
customers, draft invoices, accounts, vendors, or items. A `safe_output` mapping
can synchronize a complete provider snapshot into a plugin records resource.
One proposal uses the existing drawer; multiple proposals use import preview.
Every target requires an exact proposal grant, and no write occurs before the
user confirms.

## Do not use in new plugins

- `third_party` or legacy opaque workflow extensions; new declarative
  `workflow` extensions use `definitionVersion: 1` and a supported trigger;
- `api_calls`, direct `run_api_call`, or static execution modals;
- singular action `safeOutput` or connector-level discovery aliases;
- direct extension `permissions.network` or `permissions.secrets`;
- schedules or background triggers other than `accounting.journals.committed`;
- arbitrary scripts, HTML, SQL, executable files, or response transforms;
- file inputs on actions or event workflows, pasted CSV/XLSX parsing, raw file
  access, or invented parser/validator steps; manual workflows use the host's
  declared `file` input and `dataset.read` only;
- physical table names, joins, subqueries, unions, window functions, or
  arbitrary row expressions in reports;
- report charts, dashboards, or true pivot columns in the initial v2 runtime;
- plugin-specific writers for native records or accounting tables.

If the documented extensions cannot express a requirement, stop and propose a
generic host capability. Do not create an undeclared escape hatch in a plugin.
