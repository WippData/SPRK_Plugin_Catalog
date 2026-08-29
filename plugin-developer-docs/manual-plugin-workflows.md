# Manual Plugin Workflows

Use a `workflow` extension when a user should launch a bounded, host-executed collection workflow from a plugin-owned page. Workflows are declarative data; they do not contain JavaScript, SQL, templates, external calls, schedules, or background workers.

The complete runnable example is [workflow-renewal-review](examples/workflow-renewal-review/). The machine-readable authority is [plugin-manifest.schema.json](plugin-manifest.schema.json).

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
- an exact `data.sprk` `list` grant for a native entity query;
- an exact `data.sprk` `list` and `get` grant for native reference options;
- `accounting.journal.propose.required: true` only when using `accounting.journal.preview`.

Only `trigger: {"type":"manual"}` is public. Cron, timers, event subscriptions, scheduled triggers, background execution, and legacy opaque `steps` are not valid new-plugin syntax.

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
| `file` | `{datasetRef,contentHash}` | Manual workflow only. The host stages one declared CSV/XLSX and `dataset.read` exposes normalized rows. |

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

### File input and header aliases

A manual workflow may declare a required `file` input with exact `csv`/`xlsx`
formats, 1–5,242,880 bytes, 1–500 rows, and 1–128 typed fields. Every format
must appear in the root `files.ingest` grant. A field may declare up to 16
unique, non-blank `aliases`; IDs, labels, and aliases are normalized for header
matching and must not create an ambiguous match across fields.

Selecting, analyzing, or mapping a file does not start the workflow. Submit
uses a host-issued company/plugin/workflow/input/definition-scoped reference and
content hash. Plugins never receive raw bytes or filesystem paths. Use
`dataset.read` as the first collection command; its limit is 1–500 and must be
at least the file input's declared `maxRows`.

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
| `dataset.read` | Read normalized rows from a declared required file input; manual workflows only. |
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

The omitted/default `shape: "entries"` preserves one source record to one
journal-entry template with a fixed `lines[]` array. `shape: "line_records"`
groups reviewed source rows by `entry.entryKey`; every row must resolve identical
entry header values and an explicit `sourceRecordId`, while `entry.line` maps
that row to one journal line. A line record may declare debit, credit, or both
expressions. At runtime exactly one side must resolve to a positive amount.

Optional `deduplication: {"mode":"source_record","onChange":"correction_required"}`
uses the explicit source identity to make unchanged retries idempotent. Changed
economic content cannot silently replace posted history; it requires the host's
correction path. Grouped lines retain the same review, balance, account, date,
permission, lock, audit, and exact-hash posting controls.

## Validation

Run:

```bash
python3 scripts/validate_plugin_folder.py path/to/plugin-folder
```

The local gate validates exact shapes, capabilities, target and resource references, input defaults and reference grants, source order, global IDs, branch safety, graph limits, review order, and journal-preview placement. Runtime revalidates company scope, grants, records, schema versions, context, inputs, and limits before execution.
