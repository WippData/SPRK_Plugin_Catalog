# Supported Plugin Patterns

New plugins should be assembled from these host-rendered building blocks.

## Use these extension types

| Extension | Use it for | Required pairing or limit |
| --- | --- | --- |
| `new_page` | Plugin-owned list or transaction records | Use a declared `records` resource and host-rendered fields/actions. |
| `connector` | External HTTPS authentication and operations | Pair with configuration; credentials remain host-owned. |
| `plugin_configuration` | Company settings, connections, and bindings | Exactly one configuration extension and resource per bundle. |
| `actions` | Bounded manual data/API/review operations | `trigger` is `manual`; declare exact capabilities. |
| `existing_page_actions` | Expose an action on an approved SPRK surface | Use only `kind: "run_action"`. |
| `report` | Native table reports and company-shared saved views | Use the executable `data`/table-`views` shape, exact semantic-source grants, declared filters/groups/measures, and bounded customization flags. |
| `accounting_schedule` | Host-controlled accounting schedule proposals | Requires balanced host posting and full accounting safeguards. |
| `expand_page` | Approved additions to an existing plugin page | Confirm the target host surface before depending on it. |

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

## Do not use in new plugins

- `third_party` or opaque `workflow` extensions;
- `api_calls`, direct `run_api_call`, or static execution modals;
- singular action `safeOutput` or connector-level discovery aliases;
- direct extension `permissions.network` or `permissions.secrets`;
- scheduled/background action triggers;
- arbitrary scripts, HTML, SQL, executable files, or response transforms;
- file-upload inputs, pasted CSV/XLSX parsing, or invented parser/validator steps;
- physical table names, joins, subqueries, unions, window functions, or
  arbitrary row expressions in reports;
- report charts, dashboards, or true pivot columns in the initial v2 runtime;
- plugin-specific writers for native records or accounting tables.

If the documented extensions cannot express a requirement, stop and propose a
generic host capability. Do not create an undeclared escape hatch in a plugin.
