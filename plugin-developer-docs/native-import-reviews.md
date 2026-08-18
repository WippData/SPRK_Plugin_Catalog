# Native Import Reviews

`review.import` is the terminal handoff from a plugin action to an SPRK-owned
import review. It accepts only normalized safe-output fields, stages them under
the current company and plugin action, and opens the same native review used by
the owning SPRK page. It never grants a plugin direct access to core tables or
accounting posting.

Supported targets are:

| `targetEntity` | Native destination | Required field mappings |
| --- | --- | --- |
| `bank_register` | Banking import review | `sourceTransactionId:string`, `date:date`, `amount:number` or `currency` |
| `accounts` | Chart of Accounts import review | `name:string`, `type:string` |
| `customers` | Customers import review | `name:string` |
| `vendors` | Vendors import review | `name:string` |
| `items` | Items import review | `description:string` |

Every required target field must map to a safe-output field declared with
`required: true`. Optional mappings may be omitted. A list target uses an empty
`target` object; `bank_register` requires
`{"accountId":"$context.targetId"}`.

The `source` is always an earlier connector projection with the exact shape
`$steps.<api-step-id>.safeOutput.<collection>`. It cannot point to `$inputs`, a
pasted string, a local file, or an unrestricted provider response. The action
runner does not parse CSV/XLSX files or provide general-purpose transform and
validation commands. Providers must return JSON that can be projected directly
into typed `safeOutputs` fields.

Expose the manual action with an `existing_page_actions` extension and grant
the exact host surface:

| Review target | `targetPageKey` and surface grant |
| --- | --- |
| `bank_register` | `banking.import.source.actions` |
| `accounts` | `chart` |
| `customers` | `customers` |
| `vendors` | `vendors` |
| `items` | `items` |

Bank and master-data actions use different connection context:

- `bank_register` requires `action.binding` with
  `sourceCollection: "accounts"` and `targetType: "accounts"`. The selected
  Banking candidate supplies both `$context.connectionId` and
  `$context.targetId`.
- `accounts`, `customers`, `vendors`, and `items` must omit `action.binding`.
  Their page header has no provider candidate; the host derives the action's
  connector and asks the user to select a connected company connection when
  more than one is available.

Copy the complete [bank import example](examples/review-import-bank/) or
[customer import example](examples/review-import-customers/) rather than
assembling an import bundle from isolated fragments.

## Canonical page-template fields

The master-data keys below are the same canonical keys published by
`GET /v1/import-templates` and used by the corresponding page's downloadable
template and native preview adapter. Provider field names may differ; map them
to these target keys in `review.import.fields`.

| Target | Canonical fields (`key:type`) |
| --- | --- |
| `accounts` | `name:string` (required), `type:string` (required), `code:string`, `subtype:string`, `description:string`, `nonPosting:boolean`, `controlAccount:boolean`, `reconcileAccount:boolean`, `isActive:boolean`, `parentId:string`, `parentAccountName:string` |
| `customers` | `name:string` (required), `company:string`, `email:string`, `phone:string`, `isActive:boolean`, `defaultIncomeAccountId:string`, `address1:string`, `address2:string`, `city:string`, `state:string`, `postalCode:string`, `country:string` |
| `vendors` | `name:string` (required), `company:string`, `email:string`, `phone:string`, `is1099:boolean`, `isActive:boolean`, `defaultExpenseAccountId:string`, `address1:string`, `address2:string`, `city:string`, `state:string`, `postalCode:string`, `country:string` |
| `items` | `description:string` (required), `itemType:string`, `sku:string`, `unitPrice:number`, `buyPrice:number`, `incomeAccountId:string`, `expenseAccountId:string`, `unitOfMeasure:string`, `isActive:boolean` |

`accounts.code` is conditionally required when the selected company's account
settings require codes. It is optional at bundle-install validation because a
bundle is not installed for only one company; the company-aware native preview
enforces the requirement before import.

Legacy spreadsheet headers and import aliases are parsing conveniences, not
plugin field keys. For example, a provider's `vendor_name` may map to the
plugin-safe field `providerVendor`, which then maps to the canonical target key
`name`. Do not use spreadsheet labels such as `Vendor Name` as JSON keys.

## Master-data example

Root capability:

```json
{
  "review": {
    "required": true,
    "imports": [{ "targetEntity": "customers" }]
  }
}
```

Page-surface capability:

```json
{
  "surfaces.contribute": {
    "required": true,
    "surfaces": ["customers"]
  }
}
```

Terminal action step:

```json
{
  "id": "review-customers",
  "command": "review.import",
  "with": {
    "targetEntity": "customers",
    "target": {},
    "source": "$steps.fetch.safeOutput.customers",
    "fields": {
      "name": "providerName",
      "company": "providerCompany",
      "email": "providerEmail",
      "isActive": "active"
    }
  }
}
```

The referenced safe output must declare `providerName` as required string;
the other mapped fields must have the compatible types shown above.

## Review and completion lifecycle

1. The host validates the capability grant, target-specific fields, safe-output
   types, required mappings, source expression, and terminal step position.
2. SPRK stores sanitized mapped rows in a company-scoped native preview run.
   The plugin review session retains only an opaque pointer to that run.
3. The owning page opens its existing native preview. Users can edit supported
   values, resolve duplicates, create or map account prerequisites, exclude
   rows, and confirm.
4. Native imports remain row-based and retryable. A failed or
   dependency-blocked included row keeps the plugin review pending.
5. Completion occurs only when every staged source row is either imported or
   intentionally excluded. The host verifies created record IDs against the
   correct company and native table. Generated prerequisite-account IDs do not
   count as imported customer, vendor, or item rows.

For `bank_register`, completion still occurs through the Banking confirmation
workflow. Master-data plugins do not call the completion endpoint themselves;
the host page owns that operation after native confirmation.

## Bank-register differences

Bank review retains its existing record-scoped target and optional fields:
`description`, `memo`, `checkNo`, `currency`, `vendorId`, `vendorName`,
`customerId`, and `customerName`, all strings. The optional amount transform
supports a finite, nonzero `multiply` value with absolute value no greater than
1,000,000. Master-data targets do not support the amount transform.
