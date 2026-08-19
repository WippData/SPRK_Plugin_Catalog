# Agent Decision Guide: Choose the Smallest Plugin Shape

Use this page before writing JSON. It routes a requirement to the smallest
schema-v2 extension set that the current host can execute safely.

## Start with the desired user outcome

| Desired outcome | Primary extension | Usually paired with | Important limit |
| --- | --- | --- | --- |
| Show and edit plugin-owned rows | `new_page` with `pageKind: "list"` | A `records` resource used by `page.dataSource` | The page must use host-rendered fields and actions; it cannot ship code. |
| Capture a plugin-owned transaction-like document | `new_page` with `pageKind: "transaction"` | A `records` resource, declared calculations, document metadata, and host posting declarations when applicable | Accounting impact must use canonical host posting; never create a private GL write path. |
| Call an external HTTPS endpoint | `connector` | `plugin_configuration`; often `actions` | Declare even unauthenticated external operations through the bounded connector contract. |
| Connect to an authenticated provider | `connector` | `plugin_configuration`; often `actions` | The host owns credentials and injects them only into declared operations. |
| Let a user run a bounded integration manually | `actions` | `connector` and `existing_page_actions` with `kind: "run_action"` | Only `trigger: "manual"` exists. No scheduled or background trigger is supported. |
| Let a user select, shape, group, join, and review page records | `workflow` | A resource-backed `new_page` | Manual only; selected rows are optional context and branches are bounded/data-only. |
| Put a manual action on Banking import | `existing_page_actions` | `actions` | Use `targetPageKey: "banking.import.source.actions"`, `run_action`, and the required accounts-to-accounts action binding. |
| Put a manual import action on a native master-data page | `existing_page_actions` | `actions` ending in `review.import` | Use `chart`, `customers`, `vendors`, or `items` as both page key and grant; omit action binding so the host selects a company connection. |
| Collect company settings | `plugin_configuration` | One `configuration` resource | A bundle may contain at most one configuration extension. |
| Collect a provider connection | A `connection` section inside `plugin_configuration` | A `connector` resource and matching auth method | Do not represent a secret as an ordinary configuration field. |
| Map provider accounts to SPRK accounts | A `bindings` section inside `plugin_configuration` | A preceding connection section and `plugin.bindings.manage` | Current connector discovery output supports `sourceCollection: "accounts"`. |
| Stage bank or native master data for review | `actions` ending in `review.import` | A connector `api.execute` step and a safe-output collection | Supported targets are `bank_register`, `accounts`, `customers`, `vendors`, and `items`; review must be the final step. |
| Convert selected plugin rows to native records | `actions` ending in `review.propose` | Optional `fieldMappings` plus page/row `run_action` | One proposal opens the native drawer; multiple proposals open import preview. |
| Synchronize provider rows into plugin storage | `actions` ending in `review.propose` | Safe output, plugin records resource, and full-snapshot delta mapping | Every create/update/inactivation is reviewed; missing records are marked inactive. |
| Maintain an existing direct-delta plugin | Existing `resource.apply_delta` action | Declared safe output and records resource | Compatibility-only; keep it working, but prefer reviewed snapshot proposals for new authoring. |
| Persist connector cursor state | A `host_only` records resource | Connector pagination | Cursor state requires a string `cursor` field and advances only after confirmed review. |
| Add a native custom report | A `report` extension with the executable `data`/table-`views` definition | `reports.query` plus `surfaces.contribute: ["reports.catalog.entries"]` | Discover an exact source/version, declare bounded filters/groups/measures, and render a table only. |
| Add an accounting schedule or page expansion | The matching declared extension type | Product-team coordination | Verify the intended host surface before depending on it. |

## Recommended authenticated integration pattern

Use four declarations with distinct responsibilities:

1. `connector` declares auth, HTTPS operations, timeouts, retries, variables,
   pagination, and narrow output projections.
2. `plugin_configuration` provides host-rendered settings and connection UI.
3. `actions` performs a manual, bounded sequence and declares every safe output.
4. `existing_page_actions` exposes that action on an approved host surface.

Do not collapse these responsibilities. In particular, configuration is not a
network runner, a connector is not a page, and an action does not own secrets.

## Capability selection

Start with no grants and add only those required by the declarations:

| Declaration or step | Required root capability |
| --- | --- |
| Any `connector` extension | `internetAccess.required: true` with a non-empty reason, plus `api.execute.required: true` and the exact method set |
| Any `actions` extension | `actions.run.required: true` with `allowedTriggers: ["manual"]` |
| Any `workflow` extension | `workflows.run.required: true` plus `plugin_pages.header.actions` in `surfaces.contribute` |
| Plugin-resource workflow query/reference | `records.query.required: true` |
| Workflow journal preview | `accounting.journal.propose.required: true` |
| `data.list`, `data.get`, or `data.resolve` | `data.required: true` with the exact entity and operation |
| An action binding or configuration binding | `plugin.bindings.manage.required: true` with the exact target |
| `review.import` | `review.required: true` with an `imports` grant matching the step's `targetEntity` |
| `review.propose` | `review.required: true` with an exact `proposals[].target` grant matching the field mapping |
| `run_action` on a native page | `surfaces.contribute.required: true` with the exact page key: `banking.import.source.actions`, `chart`, `customers`, `vendors`, or `items` |
| `run_action` in a plugin-page header | `surfaces.contribute.required: true` with `plugin_pages.header.actions` |

## Stop and redesign when

- The proposed bundle contains JavaScript, Go, Python, SQL, executable files,
  arbitrary HTML, or another runtime payload.
- A plugin needs to read a secret back, construct undeclared headers, execute an
  undeclared URL, or run an arbitrary response transform.
- A plugin writes directly to SPRK accounts, customers, vendors, items, bank
  registers, journal entries, or another core table.
- A background or scheduled action/workflow is essential. Public schema-v2 actions and workflows are manual.
- The requirement starts from pasted CSV, a local upload, or a spreadsheet.
  The current action runner has no file input or parser; `review.import` starts
  from an earlier connector safe output.
- Accounting would be posted without the same validation, review, permissions,
  period controls, audit, reversal, and reconciliation behavior as native UI.
- A requirement needs a surface or command not listed in the normative API docs.

## Contract authority for new plugins

When documentation and behavior disagree, use this order:

1. The typed field reference defines what a new plugin may declare.
2. Install Preview applies bundle-wide validation.
3. Current host runtime behavior determines whether the declaration is surfaced
   and executable in the selected SPRK version.
