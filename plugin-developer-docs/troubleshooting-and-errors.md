# Troubleshooting and Error Catalog

Start with the exact error class and JSON path. Do not “fix” a validation error
by broadening capabilities, removing audit controls, or changing stable IDs
without understanding the reference that failed.

## Package and root-manifest errors

| Error or symptom | Likely cause | Corrective action |
| --- | --- | --- |
| `manifest.json` not found | The parent folder was zipped instead of its contents | Rebuild the ZIP so `manifest.json` is at archive root. |
| Unsafe or duplicate archive path | Absolute path, backslash, `..`, whitespace, duplicate entry, drive path, or null byte | Use unique forward-slash relative paths only. |
| Bundle/file/manifest limit exceeded | Too many files or compressed/expanded/file size is too large | Remove non-runtime artifacts; keep under the documented limits. |
| `schemaVersion must be 2` | Number `2` or another string | Use the exact string `"2"`. |
| `<id> must use lowercase...` | ID begins incorrectly, is too long, or contains an unsupported character | Use the backend grammar: lowercase letter/number first, then lowercase letters, numbers, `.`, `_`, or `-`, maximum 128 characters. |
| Extension ID mismatch | Root reference and extension envelope differ | Make `extensionManifests[].extensionId` equal the extension file's `extensionId`. |
| SHA-256 mismatch | Extension bytes changed after the hash was calculated | Recompute the hash from the exact extension JSON bytes to be packaged. |

## Capability and cross-reference errors

| Error or symptom | Likely cause | Corrective action |
| --- | --- | --- |
| API method not granted | Operation method is absent from `api.execute.methods` | Add only that method and set `api.execute.required: true`; every new plugin must declare this explicitly. |
| Internet-access reason required | A connector/API exists but disclosure is absent | Set `internetAccess.required: true` and add a concrete reason. |
| Actions require manual capability | `actions.run` is missing or omits `manual` | Grant `actions.run` with `allowedTriggers: ["manual"]`. |
| Data/review/binding step not granted | Step exceeds the root capability | Add the exact entity/operation, review target, or binding target—or remove the step. |
| Configuration source is not declared | `$configuration.<fieldId>` has no matching fields section | Declare that non-secret field in the single configuration extension and match the ID exactly. |
| Connector operation unavailable | Connector extension/resource/operation reference is wrong, disabled, or its method is ungranted | Check all three IDs, resource kind, operation, enablement, and method capability. |
| Action reference does not exist | `run_action` targets a missing extension/action | Match the `actions` extension ID and manual action ID exactly. |
| Surface is not granted | Existing-page action lacks `surfaces.contribute` | Grant the exact `targetPageKey`: `banking.import.source.actions`, `chart`, `customers`, `vendors`, or `items`. |
| Report source not granted | Definition source/version is absent from `reports.query.sources` | Add the exact discovered source/version or remove the report; do not grant a family wildcard. |
| Report catalog entry unavailable | `reports.catalog.entries` is absent from `surfaces.contribute` or runtime is unavailable | Grant that exact surface and raise `minAppVersion` to a host that advertises report execution. |

## Resource and data errors

| Error or symptom | Likely cause | Corrective action |
| --- | --- | --- |
| Resource kind invalid for extension | Connector/configuration/ordinary extension uses the wrong resource kind | Connector: one `connector` plus optional `records`; configuration: exactly one `configuration`; other types: `records`. |
| `recordSchema` required | A non-`new_page` records resource omits its schema | Declare 1–128 uniquely named fields with supported data types. |
| Host-owned field ID | Record schema uses `id`, `recordId`, `companyId`, `pluginId`, `extensionId`, `resourceId`, `schemaVersion`, `createdAt`, or `updatedAt` | Rename the plugin-owned field and map it explicitly. |
| Pagination state resource invalid | Cursor resource is not declared, not `host_only`, or lacks the required cursor field | Reference a `host_only` records resource with required string `cursor`. |
| Proposal source unavailable | `review.propose` mapping does not reference an authorized plugin selection or earlier safe output | Match the plugin-page resource or use `$steps.<stepId>.safeOutput.<collection>` from a preceding API step. |
| Identity field invalid | Safe output or destination schema lacks a required string identity | Declare the same required string field in both places. |

## API and connector errors

| Error or symptom | Likely cause | Corrective action |
| --- | --- | --- |
| Base URL rejected | URL is non-HTTPS or otherwise unsafe | Use an external HTTPS base URL accepted by the backend validator. |
| Path must stay on base host | Absolute/relative path resolves to another hostname | Keep the operation on the declared hostname; add another approved connector only if the product design supports it. |
| GET body rejected | GET operation has a non-null body | Move values into declared query parameters or select the correct HTTP method. |
| Auth method invalid | Type-specific auth fields do not match the discriminator | Use the typed auth model and only its compatible nested object and configuration action. |
| Username/password rejected | Connector declares unsupported credential semantics | Use a supported provider auth method; do not disguise a password as an API key. |
| Retry or timeout rejected | Values are absent, inconsistent, or outside bounds | Use explicit bounded execution policy values and allowed retry conditions. |
| Safe output invalid | Missing collection/path/fields, invalid type, duplicate collection, or item bound outside 1–10,000 | Declare a narrow, typed `safeOutputs` projection. |

## Action and review errors

| Error or symptom | Likely cause | Corrective action |
| --- | --- | --- |
| Unknown field in `with` | Command-specific object contains a field from another command | Select the `with` schema by `command`; action steps use strict unknown-field rejection. |
| Step command unsupported | Typo or unimplemented command | Use `data.list`, `data.get`, `data.resolve`, `api.execute`, `review.import`, `review.propose`, or compatibility-only `resource.apply_delta`. |
| CSV/file parsing command unsupported | The plugin invented a parser, transform, or validation step | The current runner cannot ingest local files or pasted CSV/XLSX. Fetch provider JSON with `api.execute`, project typed `safeOutputs`, or report the requested primitive as unsupported. |
| More than 32 actions or 16 steps | Manifest exceeds runner bounds | Split the user workflow into smaller manual actions without creating a hidden scheduler. |
| `connectionId` invalid | API action does not use the selected host connection | Set it to `$context.connectionId`. |
| Request binding rejected | Invalid source expression or query/body destination shape | Use a declared `$context`, `$inputs`, `$configuration`, or earlier `$steps` source and the correct `name`/`path` rules. |
| Review step must be final | Another step follows `review.import` | Move review to the end; native review is the handoff boundary. |
| Review source rejected | Source points to `$inputs`, a file, or a non-API step | Use exactly `$steps.<earlier-api-step>.safeOutput.<declared-collection>`. |
| Proposal mapping missing | `review.propose` references an absent mapping ID | Add the optional `fieldMappings` entry or fix the reference. |
| Proposal grant mismatch | Mapping target differs from `review.proposals[].target` | Grant the exact target kind, entity/resource, and operation. |
| Snapshot identity invalid | Full snapshot contains blank/duplicate identities or an incomplete page set | Supply a complete bounded snapshot with a stable required identity. |
| Bank review binding missing | The action cannot obtain the selected account/connection context | Add the required accounts-to-accounts action binding and expose it on `banking.import.source.actions`. |
| Master-data review binding rejected | A page-header action incorrectly expects a provider candidate | Remove `action.binding`; the host selects a connected company connection for the action's connector. |
| Bank review fields missing | Required source transaction ID, date, or amount mapping is absent or optional | Map all three from required compatible safe-output fields. |
| Amount transform rejected | Multiplier is zero, non-finite, or unreasonably large | Use a finite nonzero multiplier whose absolute value does not exceed 1,000,000. |
| Master-data review target is not empty | An accounts, customers, vendors, or items step includes a record-scoped target | Set `target` to `{}`; only bank review uses `accountId`. |
| Master-data review field rejected | A field is unknown, has the wrong type, or a required mapping is absent/optional | Use the target's canonical template keys and map required keys from required compatible safe outputs. |
| Account code required in preview | The selected company requires account codes even though install validation accepted an optional `code` mapping | Supply a unique account `code`; this rule is company-dependent and enforced by native preview. |
| Review remains pending after import | At least one staged row failed, was not attempted, or was not intentionally excluded | Resolve dependencies or validation errors and retry included rows, or explicitly exclude rows that should not import. |

## Installation succeeds but nothing appears

Check these separately:

1. The plugin is installed application-wide.
2. The plugin and relevant extensions are enabled for the selected company.
3. Configuration and connection requirements are satisfied.
4. The extension has a current public runtime consumer.
5. `new_page` uses `list` or `transaction` and has a resource data source.
6. Direct extension permissions do not request network or secrets.
7. Install Preview reports no warnings or unavailable-runtime condition.

For `expand_page`, `report`, and `accounting_schedule`, verify the intended host
surface in the minimum SPRK version declared by the plugin.

## Manual workflow errors

| Error or symptom | Likely cause | Corrective action |
| --- | --- | --- |
| Workflow is not listed | Missing `workflows.run`, missing `plugin_pages.header.actions`, wrong target, or disabled extension | Grant the exact capabilities and target an enabled same-plugin resource-backed `new_page`. |
| Input options fail to load | Reference grant/resource/filter is invalid | Native references need exact data list/get grants; plugin references need `records.query` and a user-accessible same-plugin records resource. |
| Input value rejected | Runtime value or default does not match its rich type | Use the exact value shapes in [Manual Plugin Workflows](manual-plugin-workflows.md); arrays/maps are capped at 100. |
| Selection rejected | IDs are stale, duplicated, cross-company, wrong-resource, host-only, or over 500 | Refresh the target page and submit only its selected record IDs. Selection may be omitted. |
| Source must reference an earlier command | `$steps.ID.records` names a future, branch-private, or non-list result | Reorder commands or read the outer control command's collection. |
| Nested branch is not data-only | A branch contains query, review, loop, update, journal preview, or another side effect | Move the side effect after the outer control command and source `$steps.CONTROL_ID.records`. |
| Workflow graph limit exceeded | Branch depth, block size, graph size, or collection size exceeds its bound | Split the user-visible manual workflow; do not add a scheduler or hidden runtime. |
| Aggregate failed | A strict numeric measure encountered null or non-numeric data | Filter/normalize the plugin-owned source before aggregation or choose a valid numeric field. |
| Join failed | Right-side keys are duplicated or output exceeds 500 | Aggregate/distinct the right side first and narrow inputs. Null keys intentionally never match. |
| Workflow stopped | `control.stop` selected a completed/cancelled/failed outcome | Display the persisted stop message and correct the controlling input or data. |
| Journal preview unavailable | Proposal capability, earlier review, account/date/period validation, or terminal placement is missing | Keep journal preview terminal after one review and use the host's canonical preview/confirmation path. |

## Report query errors

| Error or symptom | Likely cause | Corrective action |
| --- | --- | --- |
| `query_invalid` | AST shape, typed value, field/operator, grouping, or customization exceeds the definition/catalog | Fix the exact validation path; never replace the AST with SQL or broaden every allowlist. |
| `report_definition_stale` | Client digest does not match installed definition | Refresh the runtime report entry and rerun against its new digest. |
| `report_definition_invalid` | Installed report JSON cannot be decoded as the executable report contract | Validate the extension against the supplied JSON Schema and backend Install Preview. |
| `report_not_found` | Composite plugin/extension/report identity does not resolve | Refresh the runtime snapshot and use all three host-provided IDs. |
| `report_source_not_granted` | Report source is not in `reports.query` | Grant the exact discovered source/version. |
| `report_surface_not_granted` | Reports catalog surface is absent | Add `reports.catalog.entries` to `surfaces.contribute`. |
| `plugin_unavailable` | Plugin/extension is disabled, quarantined, uninstalled, or absent from the company runtime snapshot | Restore a compatible enabled plugin; retained saved views do not grant execution. |
| Detail pages repeat or skip rows | Sort does not produce stable ordering | Add deterministic semantic sorts; the host should add a final stable record tie-breaker. |
| Totals disagree with native accounting | Wrong grain, basis, date, posting state, currency mode, or unsupported source semantics | Compare effective result metadata and source definition to the native report. Do not repair accounting totals in the browser. |

The current runtime does not emit the planned `field_unavailable`,
`source_version_unsupported`, `saved_view_stale`, or `budget_exceeded` codes as
a complete public error set. Handle unknown structured errors safely and use
the message plus refreshed runtime/source metadata when diagnosing them.

SPRKQL compiler errors occur before installation. `JOIN`, subqueries, comments,
DDL/DML, table names, wildcard selection, unknown functions, and raw expressions
are intentionally unsupported. Compile only against an advertised semantic
source and copy the emitted `sourceGrant`, `data`, and `views` fragment into the
root capability and executable report definition.

## Static checks pass but install preview fails

Static JSON and archive checks do not apply the full typed, conditional, and
cross-extension contract. Treat the backend install-preview error as
authoritative, fix the exact JSON path, and add the missing case to the local
test set before release.
