# Native List Drawer Fields

An `expand_page` v1 extension can add optional plugin-owned fields to the
create, view, and edit drawer of one approved native list page. The initial
allowlist is `accounts`, `customers`, `vendors`, and `items`. Transaction pages,
list columns, arbitrary layout changes, and native record fields are outside
this contract.

## Declaration

The root manifest grants the exact drawer surface:

```json
{
  "capabilities": {
    "surfaces.contribute": {
      "required": true,
      "surfaces": ["customers.drawer.fields"]
    }
  }
}
```

The extension is company-scoped and declares exactly one company-scoped,
`host_only` records resource. Because that resource is the extension's sole
resource, the host derives it without a `valueResourceId` in the definition.
Its record schema contains exactly the declared extension field IDs. All
resource fields set `required: false`; enum values use storage type `string`.
Native record identity and plugin provenance are host-owned row metadata and
must not be declared as resource fields.

```json
{
  "schemaVersion": "2",
  "extensionId": "customer-fields",
  "type": "expand_page",
  "name": "Customer fields",
  "version": "1.0.0",
  "targets": { "companyScoped": true },
  "resources": [
    {
      "resourceId": "customer-values",
      "kind": "records",
      "schemaVersion": 1,
      "scope": "company",
      "access": "host_only",
      "recordSchema": {
        "fields": [
          { "fieldId": "segment", "dataType": "string", "required": false },
          { "fieldId": "credit-limit", "dataType": "number", "required": false },
          { "fieldId": "tax-exempt", "dataType": "boolean", "required": false }
        ]
      }
    }
  ],
  "definition": {
    "definitionVersion": 1,
    "targetPageKey": "customers",
    "addFields": [
      {
        "fieldId": "segment",
        "label": "Segment",
        "dataType": "string",
        "required": false,
        "tooltip": "Internal customer grouping.",
        "ui": {
          "drawer": {
            "input": "select",
            "options": {
              "kind": "static",
              "items": [
                { "value": "retail", "label": "Retail" },
                { "value": "wholesale", "label": "Wholesale" }
              ]
            }
          }
        }
      },
      {
        "fieldId": "credit-limit",
        "label": "Credit limit",
        "dataType": "number",
        "required": false,
        "ui": { "drawer": { "input": "number" } }
      },
      {
        "fieldId": "tax-exempt",
        "label": "Tax exempt",
        "dataType": "boolean",
        "required": false,
        "ui": { "drawer": { "input": "checkbox" } }
      }
    ]
  }
}
```

The supported logical field types are string, enum, number, and boolean, using
the existing `FieldDef` wire shape. Plain strings use `dataType: "string"` with
drawer input `text` (or `textarea`); enums use `dataType: "string"`, drawer
input `select`, and a non-empty plugin-defined static options list. Numbers use
`dataType: "number"` with input `number`; booleans use `dataType: "boolean"`
with input `checkbox`. Fields omit defaults and always set `required: false`.
Field IDs and enum values are persisted compatibility contracts; change labels
instead of IDs or values when only display text changes.

The exact surface grants are:

| `targetPageKey` | Required surface |
| --- | --- |
| `accounts` | `accounts.drawer.fields` |
| `customers` | `customers.drawer.fields` |
| `vendors` | `vendors.drawer.fields` |
| `items` | `items.drawer.fields` |

## Host behavior

The normal native API request and response contracts do not gain plugin fields.
The host loads and saves extension values through the `expand_page` logical
record service, scoped by company, plugin, extension, resource, native record,
and field ID.

- Create saves the native record first, then saves extension values. If the
  second step fails, the created native record remains and the drawer offers a
  retry for the extension values.
- View loads the native record and extension values separately. Failure of the
  optional extension service does not make the native drawer unavailable.
- Edit saves native values through the normal native workflow, then saves
  extension values separately. An extension-value failure is reported without
  rolling back or concealing a successful native save.
- Multiple plugins may contribute fields to one drawer. The host groups them by
  plugin and resolves values by their full owner identity, so equal field IDs
  in different plugins or extensions do not collide.

The host validates value types and current enum membership. It does not coerce
incompatible retained values or reinterpret a missing value as a default.
Native validation, permissions, audit behavior, and canonical workflows remain
unchanged.

## Disable, uninstall, and upgrade

Disabling or uninstalling a plugin hides its drawer fields but retains its
companion values. Retained values must not block uninstall. Reinstalling the
same plugin and compatible extension/resource/field identities makes those
values visible again. A renamed, removed, or type-incompatible field remains
retained but hidden; a different plugin identity never inherits it.

Company-file export/import preserves the generic plugin-owned resource rows as
part of their existing lifecycle. Native account/customer/vendor/item exports,
imports, search, filters, sorting, and list columns do not include these fields
in v1. The host's shared physical storage layout is an implementation detail,
not part of the plugin contract and not something authors may address directly.

## Compatibility-only legacy shape

The earlier unversioned `expand_page` shape used `targetPageId`, `addFields`,
`pageActions`, and `rowActions`. It remains readable for installed-object
compatibility, but it has no public runtime consumer and must not be used for
new plugins. New native drawer-field declarations always use
`definitionVersion: 1`.
