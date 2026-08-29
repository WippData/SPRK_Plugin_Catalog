# Manual Plugin Workflows

Use a manual `workflow` when a user should launch a bounded, host-executed collection workflow from a plugin-owned page. Workflows are declarative data; they do not contain JavaScript, SQL, templates, external calls, or schedules. For the separate narrow journal-commit lifecycle hook, see [Journal-Commit Event Workflows](event-driven-workflows.md).

Complete runnable examples are [workflow-renewal-review](examples/workflow-renewal-review/)
and [workflow-file-review](examples/workflow-file-review/). The machine-readable
authority is [plugin-manifest.schema.json](plugin-manifest.schema.json).

## Envelope and grants

The public authoring contract is root `schemaVersion: "2"` and workflow `definitionVersion: 1`:

```json
{
  "schemaVersion": "2",
  "extensionId": "renewal-workflows",
  "type": "workflow",
  "name": "Renewal workflows",
  "version": "1.0.0",
  "definition": {
    "definitionVersion": 1,
    "workflows": [
      {
        "workflowId": "review-renewals",
        "name": "Review renewals",
        "targetExtensionId": "renewals-page",
        "trigger": { "type": "manual" },
        "inputs": [],
        "commands": []
      }
    ]
  }
}
```

Every manual workflow needs:

- `workflows.run.required: true`;
- `surfaces.contribute.required: true` with `plugin_pages.header.actions`;
- a `targetExtensionId` naming a same-plugin `new_page` backed by a user-accessible `records` resource;
- `records.query.required: true` when querying that plugin resource;
- `files.ingest.required: true` with every declared `csv`/`xlsx` format when a
  workflow accepts a file input;
- an exact `data.sprk` `list` grant for a native entity query;
- an exact `data.sprk` `list` and `get` grant for native reference options;
- `accounting.journal.propose.required: true` only when using `accounting.journal.preview`.

Manual workflows use `trigger: {"type":"manual"}`. Cron, timers, scheduled triggers, arbitrary background execution, and legacy opaque `steps` are not valid new-plugin syntax. The only public event trigger is the separately constrained `accounting.journals.committed` contract.

## Inputs

The host renders and validates the same input model for actions and workflows.

| Type | Runtime value | Notes |
| --- | --- | --- |
| `text` | string | Single-line text. |
| `textarea` | string | Multi-line text. |
| `number` | finite number | JSON numbers only. |
| `boolean` | Boolean | JSON `true` or `false`. |
| `date` | `YYYY-MM-DD` | ISO calendar date. |
| `date_range` | `{startDate,endDate}` | Both ISO dates; start must not follow end. |
| `money` | `{amount,currency}` | Finite amount and three-letter uppercase currency. |
| `select` | string or string array | Set `multiple: true` for arrays; at most 100 unique values. |
| `multi_select` | string array | Compatibility alias; prefer `select` plus `multiple: true`. |
| `reference` | string or string array | Native or same-plugin record ID; at most 100 unique IDs. |
| `dimension_assignments` | object | Dimension type ID to dimension value ID; at most 100 assignments. |
| `file` | staged-dataset reference | Manual workflow only. The host stages a user-selected CSV/XLSX file; the submitted value is `{datasetRef,contentHash}`. |

Every input has `inputId`, `label`, `type`, optional `description`, optional `required`, and an optional type-matched `defaultValue`. Select options are `{value,label}` pairs with unique non-empty values.

A native reference is:

```json
{
  "inputId": "offset-account",
  "label": "Offset account",
  "type": "reference",
  "reference": {
    "kind": "native",
    "entity": "accounts",
    "accountFilter": {
      "postingOnly": true,
      "types": ["Asset", "Expense"]
    }
  }
}
```

Native entities are `accounts`, `customers`, `vendors`, and `items`. Account references may use `postingOnly`, `types`, and `subtypes`. The backend reloads every selected ID inside the active company and enforces the declared filter at execution time.

A same-plugin reference is:

```json
{
  "inputId": "related-renewals",
  "label": "Related renewals",
  "type": "reference",
  "multiple": true,
  "reference": {
    "kind": "plugin_resource",
    "extensionId": "renewals-page",
    "resourceId": "renewals",
    "labelField": "name",
    "secondaryLabelField": "status",
    "multiple": true
  }
}
```

The resource must be same-plugin, user-accessible, and declared with a record schema. The current host loads a permission-aware bounded option set of at most 100 rows and filters it locally; it does not expose cursor-paged reference search in this control. A submitted ID is validated again, so loading an option never authorizes a later write.

### File data is not a trigger

A file input belongs only to a manual workflow:

```json
{
  "inputId": "source-file",
  "label": "Data file",
  "type": "file",
  "required": true,
  "file": {
    "formats": ["csv", "xlsx"],
    "maxBytes": 5242880,
    "maxRows": 500,
    "fields": [
      { "fieldId": "customer", "label": "Customer", "dataType": "string", "required": true },
      { "fieldId": "amount", "label": "Amount", "dataType": "currency", "required": true }
    ]
  }
}
```

`formats` is a non-empty subset of the root `files.ingest.formats` grant.
`maxBytes` defaults to and cannot exceed 5 MiB; `maxRows` defaults to and cannot
exceed 500 in this phase. Declare 1–128 fields using `string`, `number`, `boolean`, `date`,
`datetime`, or `currency`. Field IDs are unique, and `id` is reserved for the
host's immutable per-row workflow identity.

The user opens the workflow modal, selects a worksheet when needed, and reviews
the host's header/type validation. Headers match declared field IDs or labels.
Staging computes a content hash
and returns an opaque company/plugin/workflow/input/definition-scoped reference.
It does not start a workflow, call an API, or write records. Clicking the host's
submit button starts the workflow with exactly:

```json
{ "datasetRef": "opaque-host-reference", "contentHash": "sha256-hex" }
```

The host requires an explicit sheet when an XLSX workbook has multiple sheets.
Raw bytes are transient and never become a workflow value; plugins receive no
filesystem path, browser `File`, formula execution, macro, external workbook
link, or arbitrary parser hook. Staged data is definition-digest and content-hash
pinned and expires after 24 hours unless discarded sooner. Once the user submits
the workflow, its normalized and derived rows become durable workflow audit data
and are included in company-file exports; the original file bytes are not retained.

This is additive to the existing plugin-page `pageActions: import` flow. That
flow continues to parse CSV/XLSX directly into the page's plugin-owned records;
it does not become a workflow trigger or silently change execution behavior.

## Execution context and selected rows

Selected rows are always optional. Authors do not add a selection declaration to the workflow definition. A launch may include:

```json
{
  "inputs": {},
  "context": {
    "selection": {
      "recordIds": ["record-1", "record-2"]
    }
  }
}
```

The host accepts at most 500 IDs, sorts them for stable request identity, and resolves them only from the target page's declared records resource. Missing, cross-company, host-only, stale-schema, or wrong-resource IDs fail closed.

The resolved context available to expressions is:

```json
{
  "companyId": "...",
  "companyCurrency": "USD",
  "invokedAt": "...",
  "pluginId": "...",
  "workflow": {
    "extensionId": "...",
    "workflowId": "...",
    "runId": "..."
  },
  "targetExtensionId": "...",
  "targetPageId": "...",
  "targetResourceId": "...",
  "selection": {
    "recordIds": [],
    "records": [],
    "count": 0
  }
}
```

`selection` is present even when empty. Supported context expression paths are the keys above, including `workflow.extensionId`, `workflow.workflowId`, `workflow.runId`, `selection.recordIds`, `selection.records`, and `selection.count`.

The host persists the resolved context and its hash with the workflow run. Stable idempotency includes the definition, inputs, target identity, and sorted selection IDs, but excludes volatile invocation time and run ID.

## Sources and expressions

Collection commands read one of:

- `$context.selection.records`;
- `$steps.COMMAND_ID.records` from an earlier list-producing command;
- `$item` only for `calculate` inside `control.for_each`.

Use `dataset.read` to make a declared file input available as a bounded
collection:

```json
{
  "id": "load-file",
  "command": "dataset.read",
  "with": { "inputId": "source-file", "limit": 500 }
}
```

Its output is `$steps.load-file.records`. `inputId` must name a required file
input. The optional limit is 1–500 and must be at least that input's `maxRows`;
all downstream workflow collections retain the existing 500-record working cap.
The host rejects an oversized collection; it never silently truncates rows.

Command IDs are globally unique across the entire workflow, including nested branches. A nested output is not a safe unconditional source outside its branch; use `$steps.CONTROL_ID.records`, which is the selected branch's final collection.

Expressions are structured JSON:

```json
{ "kind": "value", "value": 100 }
{ "kind": "field", "field": "amount", "path": "optional.nested.path" }
{ "kind": "input", "input": "threshold", "path": "amount" }
{ "kind": "context", "path": "selection.count" }
{
  "kind": "operation",
  "operator": "gte",
  "args": [
    { "kind": "field", "field": "amount" },
    { "kind": "input", "input": "minimum-amount" }
  ]
}
```

Operators are bounded arithmetic/date operations plus comparison, Boolean, string, membership, and empty/length operations. The allowlist is in the JSON Schema. Expression depth is 6; variadic operators accept at most 32 arguments. There is no script evaluation or string interpolation.

## Commands

| Command | Purpose and bounds |
| --- | --- |
| `dataset.read` | Read 1–500 normalized rows from a declared staged file input. Manual workflows only. |
| `records.query` | Query the target plugin resource, up to 500 rows, or a granted native entity, up to 200 rows. |
| `records.filter` | Apply a bounded `and`/`or` predicate tree. |
| `records.sort` | Stable sort by 1–4 fields with `asc`/`desc` and `first`/`last` null placement. |
| `records.distinct` | Keep the first record for 1–8 field keys. |
| `records.aggregate` | Group by 0–8 fields and compute 1–16 `count`, `sum`, `min`, `max`, or `average` measures. Non-numeric measure values fail the run. |
| `records.join` | `inner` or `left` equijoin on 1–4 field pairs. Right keys must be unique, null never matches, `rightPrefix` is required, and output is capped at 500. |
| `calculate` | Add number, date, string, or Boolean fields using structured expressions. |
| `control.for_each` | Run calculate-only commands for each source record with `continue` or `fail` item-error behavior. |
| `control.if` | Select `then` or optional `else`; returns the selected branch's final collection. |
| `control.switch` | Select one of at most 16 literal cases or an optional default; returns that branch's final collection. |
| `control.stop` | End its block with status `completed`, `cancelled`, or `failed` and an optional message. |
| `review.records` | Open the host-owned review surface for an earlier collection. Only one is supported. |
| `accounting.journal.preview` | Build a host-owned journal proposal from an earlier reviewed collection; it must be terminal. |

Collection outputs preserve source identity under host-owned `_workflow` lineage containing the producing `commandId` and `sourceRecordIds`.

### Branch safety

`control.if` and `control.switch` branches may contain only:

- filter, sort, distinct, aggregate, join, and calculate;
- nested bounded `control.if` or `control.switch`;
- `control.stop`.

Queries, review, loops, record updates, journal preview, external API operations, and any other side effect are rejected inside a branch. A block has at most 16 commands, the graph has at most 128 commands, and branch nesting depth is 3. Every collection command accepts no more than 500 source records.

## Accounting boundary

`accounting.journal.preview` proposes; it never posts by itself. The host owns the preview, permissions, exact-hash confirmation, balance validation, accounts, dates, closed-period policy, reconciliation effects, provenance, audit trail, and canonical posting service. Plugins cannot insert, edit, or delete journal entries directly. Corrections to posted history use the company's allowed reversal, void, supersede, or additive-adjustment workflow.

## Validation

Run:

```bash
python3 scripts/validate_plugin_folder.py path/to/plugin-folder
```

The local gate validates exact shapes, capabilities, target and resource references, input defaults and reference grants, source order, global IDs, branch safety, graph limits, review order, and journal-preview placement. Runtime revalidates company scope, grants, records, schema versions, context, inputs, and limits before execution.
