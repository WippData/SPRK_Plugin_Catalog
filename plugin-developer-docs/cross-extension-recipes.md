# Cross-Extension Recipes

These recipes show relationships, not complete manifests. Use the typed field
reference for every field and the backend install preview for final validation.

## Authenticated provider with a manual action

```text
manifest capabilities
├── internetAccess + api.execute
├── actions.run
└── surfaces.contribute

connector extension
├── connector resource
├── authMethods[]
└── api.operations[]
        ▲
plugin_configuration extension
└── connection section ───────────────┘
        ▲
actions extension
└── action.api.execute ───────────────┘
        ▲
existing_page_actions extension
└── run_action ───────────────────────┘
```

Cross-references that must agree:

- Configuration `connection.connector.extensionId` identifies the connector
  extension.
- Configuration `connection.connector.resourceId` identifies its sole
  `connector` resource.
- A connection action's `authMethodId` identifies a compatible connector auth
  method.
- Action `api.execute.connector` identifies the same connector extension,
  connector resource, and a declared operation.
- Existing-page `run_action.action` identifies the actions extension and one
  declared manual action.
- Every operation method appears in `capabilities.api.execute.methods`.

## Provider discovery and account bindings

Use this when provider accounts must be mapped to SPRK accounts.

1. On a connector operation, declare `connectionDiscovery` with an
   `accountsPath` and explicit account field paths.
2. In configuration, create a `connection` section referencing that connector.
3. Add a `discover_connection` action referencing the discovery operation.
4. Add a `bindings` section whose `connectionSectionId` points to the connection
   section, `sourceCollection` is `accounts`, and `targetType` is `accounts`.
5. Grant `plugin.bindings.manage` for `accounts`.

The host reduces provider output to the declared safe account fields. The
plugin does not receive credentials or unrestricted response bodies.

## Connector pagination with host-owned cursor state

Declare a records resource in the connector extension:

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

Then set the operation pagination `stateResource` to that extension/resource.
The validator requires exactly this ownership shape: `host_only`, `records`, a
record schema, and a required string `cursor`. Also declare bounded `maxPages`
and `maxItems`; pagination is not permission to fetch without limits.

## Fetch and persist provider deltas

1. An `api.execute` step declares one or more safe-output collections.
2. Each collection declares a bounded `maxItems` and an explicit field map.
3. A later `resource.apply_delta` step points `addedSource`,
   `modifiedSource`, or `removedSource` at an earlier safe-output collection.
4. `identityField` must be a required string in both the safe output and the
   destination record schema.
5. Choose `removedMode: "delete"` or `"mark"`. For `mark`, the destination
   resource needs the declared Boolean flag field.

At least one delta source is required. Delta sources cannot refer to a future
step or to an unrestricted provider response.

## Fetch and stage bank transactions for review

1. Grant `review` for `bank_register`.
2. Fetch data through a connector `api.execute` step.
3. Project a safe output containing required string `sourceTransactionId`,
   required date `date`, and required number/currency `amount`. Add only the
   supported optional fields that the provider actually supplies.
4. End the action with `review.import`.
5. Map `target.accountId` to `$context.targetId`.
6. Declare the action binding with `sourceCollection: "accounts"` and
   `targetType: "accounts"`. Bank review requires this selected Banking
   candidate context.
7. Expose the action on `banking.import.source.actions`.

`review.import` must be terminal. The result is staging evidence for native
review, not a direct bank-register or GL write.

See the complete [bank review import bundle](examples/review-import-bank/).

## Fetch and stage native master data for review

1. Choose `accounts`, `customers`, `vendors`, or `items` and grant that exact
   review target.
2. Fetch through a connector `api.execute` step and project a bounded safe
   output using only the canonical keys and types in
   [Native Import Reviews](native-import-reviews.md).
3. Map every required target key from a required compatible safe-output field.
4. End the action with `review.import`, set `target` to `{}`, and do not declare
   bank-only amount transforms.
5. Omit `action.binding`. The native page header has no provider candidate, so
   the host selects a connected company connection for the action's declared
   connector.
6. Expose the action on the matching `chart`, `customers`, `vendors`, or `items`
   surface and grant that surface at the root.

The owning page opens its native preview and performs the canonical writes.
Failed included rows remain retryable, intentionally excluded rows count toward
completion, and prerequisite account records do not count as imported rows.

See the complete [customer review import bundle](examples/review-import-customers/).

## Use a configuration value in an action

1. Declare the field in the bundle's single configuration extension.
2. Reference it from an API request binding as
   `$configuration.<fieldId>`.
3. Set the request destination to a supported binding location such as query or
   JSON body.

The bundle validator checks that exactly one configuration extension exists and
that the referenced field is declared. Configuration values are not credentials;
secrets belong in connector auth methods.

## Plugin-owned host-rendered page

1. Declare a `records` resource in the `new_page` extension.
2. Point `page.dataSource.kind` to `resource` and `resourceId` to that resource.
3. Give every field a stable `fieldId`, exact data type, and host-rendered UI
   configuration.
4. Treat the resource schema and field IDs as persisted compatibility contracts.

For transaction pages, declare calculations and posting relationships through
the host models. Do not add a plugin-specific core table or posting endpoint.

## Accounting schedule or posting recipe

Accounting-impacting plugins require an explicit accounting design review. Before shipping:

- Verify that debit and credit expressions balance for every accepted input.
- Identify the plugin, plugin version, schedule/template, posting run, source
  record, and reversal relationship in host audit evidence.
- Use native account selection, permissions, cutoff, closed-period, reversal,
  void, supersede, and reconciliation behavior.
- Preserve posted entries if the plugin is disabled or uninstalled.
- Keep imports or generated proposals in review/staging until the user or an
  explicitly configured trusted host workflow accepts them.
