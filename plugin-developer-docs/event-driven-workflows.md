# Journal-Commit Event Workflows

Use a journal-commit event workflow to update same-plugin records after SPRK
successfully posts journals proposed by another workflow in the same plugin.
This is a narrow lifecycle hook, not a general background-job or event-bus API.

The complete runnable example is
[workflow-depreciation-posting](examples/workflow-depreciation-posting/). The
machine-readable authority is
[plugin-manifest.schema.json](plugin-manifest.schema.json).

## Supported event and grants

The only public event is `accounting.journals.committed`. Declare:

```json
{
  "workflows.run": { "required": true },
  "records.write": { "required": true },
  "events.subscribe": {
    "required": true,
    "events": ["accounting.journals.committed"]
  }
}
```

`workflows.run` is required for every workflow extension. The event grant is an
exact allowlist. `records.write` permits only the event-only `records.update`
command against a user-accessible, company-scoped records resource declared by
a `new_page` extension in the same plugin. It does not permit native/core record
or journal writes.

An event-only bundle does not need `surfaces.contribute`. A bundle that also has
a manual workflow still grants `plugin_pages.header.actions` for that manual
workflow. A manual workflow proposing journals additionally needs
`accounting.journal.propose`; querying plugin records needs `records.query`.

## Trigger declaration and filtering

Event workflows are headless and inputless. Omit `targetExtensionId` and
`inputs`:

```json
{
  "workflowId": "record-depreciation-commit",
  "name": "Record committed depreciation",
  "trigger": {
    "type": "accounting.journals.committed",
    "filters": {
      "sourceExtensionIds": ["depreciation-workflows"],
      "sourceWorkflowIds": ["post-depreciation"]
    }
  },
  "commands": []
}
```

Each filter list is optional, contains at most 32 unique identifiers, and must
reference workflows in the same installed plugin. Omitted or empty lists match
all same-plugin journal-proposal workflows. Entries within one list are ORed;
when both lists are populated, the extension and workflow filters are ANDed.
Prefer both filters so the subscriber has an explicit, stable source contract,
and keep workflow IDs unique across the bundle so workflow-only filters remain
unambiguous.

SPRK queues this event only after the host commits the exact reviewed journal
preview through the canonical journal service. A preview, cancelled review,
failed validation, hash mismatch, or failed commit does not produce the event.
The queued run is company-scoped, tied to the active plugin definition digest,
and idempotent for its event receipt.

## Event journal collection

The read-only `$event.journals` collection contains one receipt per committed
journal:

| Field | Meaning |
| --- | --- |
| `id` | Source plugin record ID; currently equal to `sourceRecordId`. |
| `sourceRecordId` | Source-record ID supplied by the journal proposal. |
| `journalEntryId` | Native journal entry ID created by the host. |
| `date` | Committed journal accounting date. |
| `entryNo` | Committed journal entry number when present. |
| `sourcePostingId` | Exact reviewed preview hash that produced the commit. |
| `sourceHash` | Stable source hash from the proposing workflow run. |
| `debitTotal` | Committed debit total. |
| `creditTotal` | Committed credit total. |

The full persisted event envelope also records event ID/type, company,
occurrence time, and source plugin/extension/workflow/run/import/preview
provenance. Workflow commands intentionally consume only the bounded journal
collection.

## `records.update`

`records.update` must be the final top-level command of an
`accounting.journals.committed` workflow. It cannot appear in a manual workflow,
branch, or `control.for_each` body.

```json
{
  "id": "update-asset-posting-metadata",
  "command": "records.update",
  "with": {
    "resource": {
      "extensionId": "assets-page",
      "resourceId": "assets"
    },
    "source": "$event.journals",
    "recordId": { "kind": "field", "field": "sourceRecordId" },
    "set": {
      "last_depreciation_date": { "kind": "field", "field": "date" },
      "last_journal_entry_id": { "kind": "field", "field": "journalEntryId" },
      "last_posting_hash": { "kind": "field", "field": "sourcePostingId" }
    }
  }
}
```

`source` may be `$event.journals` or an earlier list-producing command. The
`recordId` and 1–32 `set` values use bounded workflow expressions. Every source
row must resolve to a unique, non-empty existing record ID. The host validates
the complete updated row against the declared resource schema and account
references, then applies at most 500 same-plugin mutations transactionally.
`host_only` resources and resources outside the active company/plugin are
rejected.

An event workflow that performs data-only work and does not use
`records.update` does not need `records.write`.

Use writeback for derived schedule metadata such as the native journal ID,
posting date, and posting hash. Do not treat plugin writeback as the accounting
source of truth; the GL remains authoritative.

## Accounting and lifecycle boundary

The supported event reports successful journal creation only. There are no
public journal reversed, voided, superseded, corrected, edited, or deleted
events. Therefore:

- never claim that plugin schedule state automatically follows later journal
  corrections;
- keep native journal IDs and posting hashes so state can be reconciled to the
  GL;
- preserve posted history when a plugin is disabled or uninstalled; and
- use the company's canonical reversal, void, supersede, or additive-correction
  workflow for posted accounting.

The event workflow cannot propose another journal, call a connector, mutate a
native record, run arbitrary code, or schedule itself.

## Validation

Run:

```bash
python3 scripts/validate_plugin_folder.py path/to/plugin-folder
```

The local gate validates the exact event grant, headless/inputless shape,
same-plugin filter references, event-only source and update placement,
`records.write`, and the target extension/resource/access contract. Runtime
revalidates company/plugin/definition identity, idempotency, resource schema,
record IDs, account references, and the 500-record limit before writeback.
