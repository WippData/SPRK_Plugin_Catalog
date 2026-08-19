# Plugin Syntax Models

This is a compact map of the SPRK schema-v2 plugin format. For new plugins,
the normative field-by-field contract is the [Typed Field Reference](schema-v2-field-reference.md)
and [Machine-Readable JSON Schema](plugin-manifest.schema.json).

## Common values

Plugin-defined IDs must start with a lowercase letter or number and otherwise
contain only lowercase letters, numbers, periods, underscores, or hyphens.

| Item | Allowed values |
| --- | --- |
| Plugin schema version | `"2"` |
| Resource schema version | `1` |
| Record field `dataType` | `string`, `number`, `boolean`, `date`, `datetime`, `currency` |
| HTTP method | `GET`, `POST`, `PUT`, `PATCH`, `DELETE` |
| Page kind | `list`, `transaction`, `accounting_schedule` |
| Action trigger | `manual` |
| Workflow trigger | `{ "type": "manual" }` |

## Root manifest

```json
{
  "schemaVersion": "2",
  "pluginId": "publisher.plugin-name",
  "name": "Display name",
  "version": "1.0.0",
  "publisher": {
    "id": "publisher",
    "name": "Publisher name",
    "supportEmail": "support@example.com",
    "website": "https://example.com"
  },
  "description": "Optional description",
  "runtime": { "minAppVersion": "1.0.0", "maxAppVersion": "1.9.0" },
  "capabilities": {},
  "extensionManifests": [
    {
      "extensionId": "actions",
      "path": "extensions/actions.json",
      "sha256": "optional hexadecimal SHA-256"
    }
  ],
  "signing": { "signature": "optional", "publicKeyId": "optional" }
}
```

Required fields: `schemaVersion`, `pluginId`, `name`, `version`,
`publisher.id`, `publisher.name`, and `runtime.minAppVersion`. Every extension
reference needs a unique `extensionId` and `path`.

## Extension envelope

```json
{
  "schemaVersion": "2",
  "extensionId": "actions",
  "type": "actions",
  "name": "Display name",
  "version": "1.0.0",
  "description": "Optional description",
  "targets": { "companyScoped": true, "supportedEntityIds": [] },
  "permissions": { "network": false, "secrets": false },
  "resources": [],
  "definition": {}
}
```

Required fields: `schemaVersion`, `extensionId`, `type`, `name`, `version`,
and `definition`. `connector` and `plugin_configuration` must be company
scoped.

## Resources

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

`kind` is `records`, `connector`, or `configuration`; all resources use
`scope: "company"`. `access` is `user` or `host_only`. A records resource
normally has `recordSchema`. A connector extension needs exactly one connector
resource; a configuration extension needs exactly one configuration resource.

## Definition shapes by extension type

| Type | Required definition shape |
| --- | --- |
| `new_page` | `page` (`pageId`, `pageKind`, `title`, optional icon/route/data source), plus list or transaction fields/actions. |
| `expand_page` | `targetPageId`, `pageActions`, `rowActions`, and optional `addFields`. |
| `accounting_schedule` | `schedule`, `calculation`, and `posting`; optional templates, fields, relation roles, and account roles. |
| `report` | Optional `definitionVersion: "2"`, `report`, `data`, table `views`, and optional `customization`. Parameters and top-level source/query/table shapes are not supported. |
| `connector` | `authMethods` and `api`; `api` has `baseUrl`, `executionPolicy`, and `operations`. |
| `actions` | `actions`, each with an ID, label, `trigger: "manual"`, optional binding/inputs, and bounded steps. |
| `workflow` | `definitionVersion: 1` and `workflows`; each workflow targets a resource-backed plugin page and declares manual trigger, optional typed inputs, and bounded commands. |
| `plugin_configuration` | `title`, optional description, and `sections` of type `fields`, `connection`, or `bindings`. |
| `existing_page_actions` | `targetPageKey` and one or more `run_action` actions. |

## Important submodels

### Actions and existing-page actions

An action step has a unique `id`, a `command`, and a command-specific `with`
object. Supported commands: `data.list`, `data.get`, `data.resolve`,
`api.execute`, `review.import`, `review.propose`, and compatibility-only
`resource.apply_delta`. Inputs use `text`,
`number`, `boolean`, `date`, or `select`.

An existing-page action that invokes an action is:

```json
{
  "actionId": "sync",
  "label": "Sync now",
  "kind": "run_action",
  "action": { "extensionId": "actions", "actionId": "sync" }
}
```

`run_action` is the only existing-page action kind in the new-plugin contract.
Older direct API-action shapes are compatibility-only and are intentionally
excluded from this guide and its JSON Schema.

### Manual workflows

Workflow inputs use `text`, `textarea`, `number`, `boolean`, `date`,
`date_range`, `money`, `select` (optionally multiple), `reference`, or
`dimension_assignments`. Sources are `$context.selection.records`, an earlier
`$steps.COMMAND_ID.records`, or `$item` inside calculate-only `control.for_each`.

Commands are `records.query`, `records.filter`, `records.sort`,
`records.distinct`, `records.aggregate`, `records.join`, `calculate`,
`control.for_each`, `control.if`, `control.switch`, `control.stop`,
`review.records`, and `accounting.journal.preview`. See
[Manual Plugin Workflows](manual-plugin-workflows.md) for exact models,
structured expressions, context paths, branch restrictions, and graph limits.

For a native import action, set the extension's `targetPageKey` to the granted
surface: `banking.import.source.actions`, `chart`, `customers`, `vendors`, or
`items`. End the referenced action with `review.import` and use the matching
review target. See [Native Import Reviews](native-import-reviews.md).

### Configuration and connections

A configuration `fields` section contains fields with `fieldId`, `label`,
`type`, `required`, optional description/default, and select options. Field
types are `text`, `textarea`, `number`, `boolean`, and `select`.

A connection section references a connector with
`connector.extensionId` and `connector.resourceId`, and uses actions of kind
`configure_credentials`, `authorize_oauth2`, `authorize_hosted`, or
`discover_connection`. A bindings section identifies a connection section and
declares `sourceCollection` and `targetType`.
