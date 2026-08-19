# Reviewed Record Proposals

`review.propose` is the terminal handoff for converting plugin-owned records or
normalized provider rows into host-owned records. The plugin declares a reusable
field mapping; SPRK reloads and authorizes the source, stages proposed changes,
and owns the drawer or import-preview confirmation and canonical write.

No proposal is an automatic write. One actionable row opens the destination's
existing drawer. Multiple actionable rows open the existing import preview.
Saving the drawer or confirming the preview is the review decision; there is no
second plugin-controlled confirmation.

Complete examples cover [lead-to-customer conversion](examples/review-convert-crm/)
and a [reviewed provider snapshot](examples/review-sync-plugin-records/).

## Optional field mappings

`fieldMappings` is optional on an `actions` definition and is needed only when
an action ends in `review.propose`. Each referenced mapping owns its source,
target, target-to-source field map, optional writeback, and optional snapshot
delta. Mapping IDs are unique within the actions extension.

```json
{
  "fieldMappings": [
    {
      "mappingId": "customer-from-lead",
      "source": {
        "kind": "plugin_selection",
        "extensionId": "crm-page",
        "resourceId": "leads"
      },
      "target": {
        "kind": "native",
        "entity": "customers",
        "operation": "create_or_link"
      },
      "fields": {
        "name": { "from": "lead_name" },
        "company": { "from": "company_name" },
        "email": { "from": "email" }
      },
      "writeback": {
        "targetIdField": "customer_id",
        "operationField": "conversion_operation"
      }
    }
  ],
  "actions": [
    {
      "actionId": "convert-leads",
      "label": "Convert leads",
      "trigger": "manual",
      "steps": [
        {
          "id": "review-customers",
          "command": "review.propose",
          "with": { "mappingId": "customer-from-lead" }
        }
      ]
    }
  ]
}
```

Each field-map value declares exactly one of `{ "from": "source-field" }` or
`{ "value": <string, number, or boolean> }`. The host target adapter owns other
defaults and canonical DTO construction. Plugins cannot supply expressions,
scripts, API routes, table names, invoice status, or direct persistence logic.
The existing bank-import amount multiplication remains confined to
`review.import`.

## Sources and targets

`plugin_selection` references a same-plugin `new_page` records resource. A row
action supplies one host-authorized record ID; a page action supplies explicit
selected IDs. The backend reloads the records under the current company and
does not trust submitted row data. Selecting all rows through the current filter
is not part of this contract.

`safe_output` references exactly
`$steps.<earlier-step>.safeOutput.<collection>`. The action must project provider
JSON into bounded typed fields before proposal mapping.

Supported native targets are:

| Entity | Operation | Confirmed result |
| --- | --- | --- |
| `customers` | `create_or_link` | Create a customer or explicitly link an existing customer. |
| `accounts`, `vendors`, `items` | `create` | Create through the canonical native service. |
| `invoices` | `create_draft` | Create a non-posting draft invoice only. |
| `bills` | `create_draft` | Create a non-posting draft bill only. |
| `journal_entries` | `post` | Post a balanced journal only after explicit native-drawer confirmation. |

Invoice and bill proposals accept their native header fields and `lines[]`; the
one-line shorthand remains available for simple conversions. Their statuses are
host-forced to draft. Journal proposals accept `entryNo`, `date`, `memo`,
`vendorId`, `lines[]`, `addToBankRegister`, and `autoReverse`. Company, status,
totals, provenance, settlement, and posting overrides are always host-owned.

One native proposal opens the first-party drawer for that entity. Bulk proposals
use the shared preview, and editing a row opens the same native drawer before the
final confirmation. A journal confirmation posts immediately and therefore uses
the ordinary balance, control-account, cutoff, reconciliation, audit, and
auto-reversal rules.

Every target needs an exact `review.proposals[].target` capability grant. The
grant must match kind, entity/resource, and operation; a broader write grant is
not available.

## Plugin page actions

Host-rendered list and transaction pages may include `run_action` entries in
`pageActions` or `rowActions`. The referenced action must end in
`review.propose`, and its `plugin_selection` source must match that page's data
resource.

```json
{
  "actionId": "convert-lead",
  "enabled": true,
  "label": "Convert to customer",
  "kind": "run_action",
  "action": {
    "extensionId": "crm-actions",
    "actionId": "convert-leads"
  }
}
```

Grant `surfaces.contribute` for `plugin_pages.header.actions` when contributing
a plugin-page header action. Row actions use the same bounded action reference.

## Reviewed API snapshot synchronization

A provider may propose adding or updating plugin-owned rows. Use a complete
safe-output snapshot, a `plugin_resource` target, and this exact delta policy:

```json
{
  "source": {
    "kind": "safe_output",
    "path": "$steps.fetch.safeOutput.customers"
  },
  "target": {
    "kind": "plugin_resource",
    "extensionId": "customer-page",
    "resourceId": "provider-customers",
    "operation": "sync_snapshot"
  },
  "fields": {
    "external_id": { "from": "external-id" },
    "name": { "from": "display-name" }
  },
  "delta": {
    "mode": "full_snapshot",
    "identityField": "external_id",
    "missing": "mark_inactive",
    "inactiveField": "is_inactive"
  }
}
```

The host calculates creates, changed mapped fields, unchanged rows, missing
managed identities, and reactivations. Missing records are marked inactive;
they are never silently deleted. Unmapped user-owned fields are preserved.
Blank or duplicate identities, incomplete snapshots, duplicate managed targets,
and stale target versions block confirmation.

Provider cursor state remains pending during review. Cancellation or failure
does not advance it. The cursor advances only when every included proposal has
succeeded and exclusions have been acknowledged.

## Confirmation and completion

The host confirmation request uses proposal decisions rather than accepting
unverified created IDs:

```json
{
  "decisions": [
    { "proposalId": "proposal-1", "decision": "accept", "values": { "name": "Acme" } },
    { "proposalId": "proposal-2", "decision": "link", "targetId": "customer-42" },
    { "proposalId": "proposal-3", "decision": "exclude" }
  ]
}
```

`accept` may include edited allowlisted values, `link` requires a same-company
target ID and is available only to targets that support linking, and `exclude`
records an intentional omission. The backend revalidates source freshness,
target versions, permissions, mapping and definition digests, and canonical
business rules before committing.

Successful conversion records durable provenance and then performs declared
writeback. Retrying a completed source resolves its existing target instead of
creating a duplicate. Cancellation writes neither target records nor writeback.

`review.import` remains supported for existing safe-output bank and native
master-data imports and uses the same host staging and preview foundation.
