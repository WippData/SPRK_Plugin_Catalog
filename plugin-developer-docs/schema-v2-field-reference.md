# Schema-v2 Typed Field Reference

This is the author-facing field contract for SPRK declarative plugin bundles. JSON keys use their exact serialized spelling. The backend SDK types and validators remain authoritative.

The reference covers fields authors may place in `manifest.json` or an extension manifest. It does not describe install-preview, runtime-response, or report-query DTOs returned by the host.

## Reading the tables

- **R**: always required by validation.
- **C**: conditionally required; read the constraint.
- **O**: optional. Omitted values normally decode to the JSON type's Go zero value.
- `T[]` means an array whose every item has type `T`.
- `Record<string, T>` means a JSON object with arbitrary string keys and values of type `T`.
- `JSON` means one valid JSON value. A more specific JSON type is shown whenever validation imposes one.
- Plugin identifiers match `^[a-z0-9][a-z0-9._-]{0,127}$`.
- Extension `definition` shapes are selected by extension `type`. Action-step `with`, configuration section, transaction expression, and existing-page action shapes are selected by their discriminator fields.

## Common enums

| Type | Allowed values |
| --- | --- |
| `ExtensionType` | `new_page`, `expand_page`, `accounting_schedule`, `report`, `connector`, `actions`, `workflow`, `plugin_configuration`, `existing_page_actions` |
| `DataType` | `string`, `number`, `boolean`, `date`, `datetime`, `currency` |
| `PluginHTTPMethod` | `GET`, `POST`, `PUT`, `PATCH`, `DELETE` |
| `PluginBindingSourceCollection` | `accounts`, `customers`, `items`, `vendors` |
| `PluginBindingTargetType` | `accounts`, `customers`, `items`, `vendors` |
| `PluginActionTrigger` | `manual` |

## Root `manifest.json`

### `PluginManifest`

| Field | JSON type | Req. | Constraints and meaning |
| --- | --- | --- | --- |
| `schemaVersion` | string | R | Must be `"2"`. |
| `pluginId` | string | R | Plugin identifier; persistent bundle identity. |
| `name` | string | R | Non-blank display name. |
| `version` | string | R | Non-blank plugin version. Upgrade logic requires a newer version. |
| `publisher` | `Publisher` | R | Publisher identity. |
| `description` | string | O | Author-facing description. |
| `runtime` | `RuntimeRequirements` | R | Host-version compatibility. |
| `capabilities` | `PluginCapabilities` | R | Bounded grants and install disclosures. Use `{}` when none are needed. |
| `extensionManifests` | `ExtensionManifestRef[]` | O | Referenced extension files; `extensionId` values must be unique. |
| `signing` | `SigningInfo` | O | Serialized signing metadata. |

### `Publisher`

| Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- |
| `id` | string | R | Non-blank publisher ID. |
| `name` | string | R | Non-blank publisher name. |
| `supportEmail` | string | O | Support contact. |
| `website` | string | O | Publisher website. |

### `RuntimeRequirements`

| Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- |
| `minAppVersion` | string | R | Non-blank minimum SPRK version. |
| `maxAppVersion` | string | O | Maximum compatible SPRK version. |

### `ExtensionManifestRef`

| Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- |
| `extensionId` | string | R | Unique within the root manifest; must equal the extension file's declared ID. |
| `path` | string | R | Relative archive path validated by bundle import. |
| `sha256` | string | O | Hexadecimal digest; when present it must match the file. |

### `SigningInfo`

| Field | JSON type | Req. | Meaning |
| --- | --- | --- | --- |
| `signature` | string | O | Serialized signature value. |
| `publicKeyId` | string | O | Serialized public-key identifier. |

## Capabilities

### `PluginCapabilities`

All properties are typed objects. They may be omitted in JSON because missing object fields decode to their zero values, but authors should declare every capability they use.

| Field | JSON type | Req. | Purpose |
| --- | --- | --- | --- |
| `internetAccess` | `PluginInternetAccess` | C | Required for `connector`; installation disclosure. |
| `api.execute` | `PluginAPIExecuteCapability` | C | Enforceable HTTP-method grant. |
| `plugin.bindings.manage` | `PluginBindingsManageCapability` | C | Required for declared bindings. |
| `actions.run` | `PluginActionsRunCapability` | C | Required for an `actions` extension and `run_action`. |
| `data` | `PluginDataCapability` | C | Required by `data.*` action steps. |
| `review` | `PluginReviewCapability` | C | Required by `review.import` and `review.propose`. |
| `surfaces.contribute` | `PluginSurfacesContributeCapability` | C | Required to contribute actions to an approved core surface. |
| `reports.query` | `PluginReportsQueryCapability` | C | Required for every report source; exact source/version grants. |
| `workflows.run` | `{required: boolean}` | C | Required for a workflow extension. |
| `files.ingest` | `FilesIngestCapability` | C | Required when a manual workflow declares a file input. |
| `records.query` | `{required: boolean}` | C | Required for plugin-record queries and plugin-resource reference options. |
| `records.write` | `{required: boolean}` | C | Reserved for host-supported plugin-record updates; never a native write grant. |
| `accounting.schedules.manage` | `{required: boolean}` | C | Required by public v2 accounting schedules. |
| `accounting.journal.propose` | `{required: boolean}` | C | Required for workflow journal previews and host-reviewed schedule journal proposals; posting remains host-owned and direct GL writes are never granted. |

### Capability submodels

| Model | Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- | --- |
| `PluginInternetAccess` | `required` | boolean | R | Must be `true` when a connector executes external HTTP. |
|  | `reason` | string | C | Non-blank when `required` is true. |
| `PluginAPIExecuteCapability` | `required` | boolean | R | Must be true for new bundles that execute HTTP. |
|  | `methods` | `PluginHTTPMethod[]` | C | Non-empty when required; no duplicates; must cover every API/connector operation. |
| `PluginBindingsManageCapability` | `required` | boolean | R | True when a binding is declared. |
|  | `targets` | `PluginBindingTargetType[]` | C | Non-empty when required; no duplicates. |
| `PluginActionsRunCapability` | `required` | boolean | R | True when actions are declared. |
|  | `allowedTriggers` | `PluginActionTrigger[]` | C | Must contain `manual` when required; no duplicates or other values. |
| `PluginDataCapability` | `required` | boolean | R | True when a `data.*` step is used. |
|  | `sprk` | `PluginDataEntityGrant[]` | C | Non-empty when required. |
| `PluginReviewCapability` | `required` | boolean | R | True when `review.import` or `review.propose` is used. |
|  | `imports` | `PluginReviewImportGrant[]` | C | Exact legacy import grants; at least one import or proposal grant when required. |
|  | `proposals` | `PluginReviewProposalGrant[]` | C | Exact proposal target grants; at least one import or proposal grant when required. |
| `PluginSurfacesContributeCapability` | `required` | boolean | R | True when contributing to a core surface. |
|  | `surfaces` | `PluginSurface[]` | C | Approved native surfaces, `reports.catalog.entries`, or `plugin_pages.header.actions`; non-empty when required and no duplicates. |
| `PluginReportsQueryCapability` | `required` | boolean | R | True when executing a report. |
|  | `sources` | `ReportSourceGrant[]` | C | Non-empty exact source allowlist when required. |
| `FilesIngestCapability` | `required` | boolean | R | Must be true when a workflow declares a file input. |
|  | `formats` | string[] | R | One or both of `csv`, `xlsx`; unique and exact. |
| `ReportSourceGrant` | `sourceId` | string | R | Semantic source ID, never a table name. |
|  | `sourceVersion` | string | R | Exact advertised version. |

### Grant items

| Model | Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- | --- |
| `PluginDataEntityGrant` | `entity` | string | R | `accounts`, `customers`, `items`, or `vendors`. |
|  | `operations` | `PluginDataOperation[]` | R | One or more of `list`, `get`, `resolve`; no duplicates per grant. |
| `PluginReviewImportGrant` | `targetEntity` | string | R | `bank_register`, `accounts`, `customers`, `vendors`, or `items`. |
| `PluginReviewProposalGrant` | `target` | `ActionProposalTarget` | R | Exact kind/entity/resource/operation grant. |

Every new plugin that executes HTTP must explicitly declare `api.execute` with the smallest method set it needs.

## Extension envelope and resources

### `ExtensionManifest`

| Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- |
| `schemaVersion` | string | R | Must be `"2"`. |
| `extensionId` | string | R | Plugin identifier; must match the root reference. |
| `type` | `ExtensionType` | R | Selects the exact `definition` model. |
| `name` | string | R | Non-blank display name. |
| `version` | string | R | Non-blank extension version. |
| `description` | string | O | Description. |
| `targets` | `ExtensionTargets` | C | Required with `companyScoped: true` for connector and configuration extensions. |
| `permissions` | `ExtensionPerms` | O | Direct network/secret requests. Connector cannot request secrets; configuration cannot request network or secrets. |
| `resources` | `PluginResourceManifest[]` | O/C | IDs unique within extension. Connector requires exactly one connector resource; configuration requires exactly one configuration resource. |
| `definition` | object | R | Exact object type selected by `type`. |

### Envelope submodels

| Model | Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- | --- |
| `ExtensionTargets` | `companyScoped` | boolean | R | Must be true for connector/configuration. |
|  | `supportedEntityIds` | `string[]` | O | Declared supported entity IDs. |
| `ExtensionPerms` | `network` | boolean | O | Cannot be true for configuration. |
|  | `secrets` | boolean | O | Cannot be true for connector or configuration. |

### `PluginResourceManifest`

| Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- |
| `resourceId` | string | R | Plugin identifier; unique within extension. |
| `kind` | string | R | `records`, `connector`, or `configuration`, subject to extension-type restrictions. Non-connector/configuration extensions accept only `records`. |
| `schemaVersion` | integer | R | Must be `1`. |
| `scope` | string | R | Must be `company`. |
| `access` | string | O | `user` or `host_only`; `host_only` only for `records`. |
| `recordSchema` | `PluginRecordSchema` | C | Required for `records`, except a `new_page` records resource may omit it. Invalid for other kinds. |

### Record schema

| Model | Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- | --- |
| `PluginRecordSchema` | `fields` | `PluginRecordField[]` | R | 1–128 fields. |
| `PluginRecordField` | `fieldId` | string | R | Plugin identifier; unique. Host-owned IDs are forbidden: `id`, `recordId`, `companyId`, `pluginId`, `extensionId`, `resourceId`, `schemaVersion`, `createdAt`, `updatedAt`. |
|  | `dataType` | `DataType` | R | Closed enum. |
|  | `required` | boolean | O | Whether each record must contain the field. |

## Shared page, field, action, and import models

### `NewPageConfig` and `DataSource`

| Model | Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- | --- |
| `NewPageConfig` | `pageId` | string | R | Non-blank. |
|  | `pageKind` | string | R | `list`, `transaction`, or `accounting_schedule`; `transaction` selects `TransactionPageDefinition`. |
|  | `title` | string | R | Non-blank. |
|  | `icon` | string | O | Host icon identifier. |
|  | `route` | string | O | Host route. |
|  | `dataSource` | `DataSource` | O/C | Required for transaction pages. Resource must exist in same extension. |
| `DataSource` | `kind` | string | R | Validator currently requires `resource`; `query` is serialized but rejected here. |
|  | `resourceId` | string | R | Plugin identifier referencing an extension resource. |
|  | `where` | JSON | O | Declarative filter payload; no narrower validator contract currently exists. |
|  | `sort` | JSON | O | Declarative sort payload; no narrower validator contract currently exists. |

### `FieldDef`

| Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- |
| `fieldId` | string | R | Non-blank. Transaction fields must also be unique in their section and cannot use `id`, `companyId`, `createdAt`, `updatedAt`, `isActive`, `status`, `header`, `lines`, `totals`, `linkedJournalEntryId`. |
| `label` | string | R | Non-blank. |
| `dataType` | `DataType` | R | Closed enum. |
| `required` | boolean | R | Requiredness of the value. |
| `tooltip` | string | O | Host-rendered help. |
| `defaultValue` | JSON | O | Any JSON value; current general-field validation does not narrow it by `dataType`. |
| `ui` | `FieldUI` | O | Host rendering declarations. |

### Field UI

| Model | Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- | --- |
| `FieldUI` | `table` | `FieldUITable` | O | Table rendering. |
|  | `drawer` | `FieldUIDrawer` | O | Drawer rendering. |
| `FieldUITable` | `visible` | boolean | O | Visibility. |
|  | `width` | integer | O | Column width. |
| `FieldUIDrawer` | `input` | string | R | `text`, `textarea`, `number`, `date`, `datetime`, `select`, `multiselect`, `checkbox`, `reference`, `page_link`. |
|  | `visible` | boolean | O | Visibility. |
|  | `options` | `DrawerOptions` | O | Select-like options. |
|  | `pageLink` | `DrawerPageLink` | C | Required for `input: page_link`. |
|  | `reference` | `DrawerReference` | O | Reference-picker configuration. |
| `DrawerOptions` | `kind` | string | R | `static` or `query`. |
|  | `items` | `DrawerOption[]` | C | Non-empty for `static`. |
| `DrawerOption` | `value` | string | R | Non-blank. |
|  | `label` | string | R | Non-blank. |
| `DrawerPageLink` | `targetPageId` | string | R | Non-blank. |
|  | `paramMap` | `Record<string, string>` | O | Source-to-target parameter mapping. |
|  | `filter` | `AccountReferenceFilter` | O | Native Accounts target only; may require active posting accounts and bound account types/subtypes. |
| `DrawerReference` | `sourcePageId` | string | R | Non-blank. |
|  | `valueField` | string | R | Non-blank. |
|  | `labelField` | string | R | Non-blank. |
|  | `allowCreateInline` | boolean | O | Allows host inline creation. |

### Built-in/custom page actions

`ActionDef.actionId` is a union: a built-in action string or a `CustomAction` object.

| Model | Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- | --- |
| `ActionDef` | `actionId` | string or `CustomAction` | R | Page built-ins: `new`, `refresh`, `import`, `export_csv`, `export_xlsx`. Row built-ins: `view`, `edit`, `delete`. |
|  | `enabled` | boolean | R | Enables the action. |
| `CustomAction` | `actionId` | string | R | Must be `custom`. |
|  | `key` | string | R | Non-blank custom key. |
|  | `label` | string | R | Non-blank display label. |
|  | `icon` | string | O | Host icon identifier. |
|  | `enabled` | boolean | O | Custom action enablement. |
|  | `futureWorkflow` | string | O | Future workflow declaration. |

### Import templates

At least one column must exist across `requiredColumns`, `optionalColumns`, and `templateColumns`; column names are unique case-insensitively across all three arrays.

| Model | Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- | --- |
| `ImportTemplateDefinition` | `key` | string | O | Template key. |
|  | `templateName` | string | O | Display name. |
|  | `fileName` | string | O | Suggested file name. |
|  | `acceptedFormats` | `string[]` | O | Items must be non-blank. |
|  | `requiredColumns` | `ImportTemplateColumn[]` | O/C | Participates in at-least-one-column rule. |
|  | `optionalColumns` | `ImportTemplateColumn[]` | O/C | Same. |
|  | `templateColumns` | `ImportTemplateColumn[]` | O/C | Same. |
|  | `notes` | `string[]` | O | Template notes. |
|  | `sampleRows` | `Record<string, JSON>[]` | O | Sample row objects. |
|  | `sheetName` | string | O | Worksheet name. |
|  | `blankRowCount` | integer | O | Non-negative. |
|  | `referenceSheets` | `ImportTemplateReferenceSheet[]` | O | Supplemental sheets. |
| `ImportTemplateColumn` | `name` | string | R | Non-blank, unique case-insensitively across all column lists. |
|  | `key` | string | O | Column key. |
|  | `required` | boolean | O | Required marker. |
|  | `description` | string | O | Description. |
| `ImportTemplateReferenceSheet` | `name` | string | R | Non-blank. |
|  | `columns` | `string[]` | R | Non-empty; every string non-blank. |
|  | `rows` | `Record<string, JSON>[]` | O | Reference rows. |

## `new_page` definition

For `page.pageKind: "transaction"`, use `TransactionPageDefinition`; otherwise use `NewPageDefinition`.

### `NewPageDefinition`

| Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- |
| `page` | `NewPageConfig` | R | Non-transaction page configuration. |
| `fields` | `FieldDef[]` | O | Host-rendered fields. |
| `importTemplate` | `ImportTemplateDefinition` | O | Import template. |
| `pageActions` | `ActionDef[]` | O | Standard page actions or `run_action` references. |
| `rowActions` | `ActionDef[]` | O | Standard row actions or `run_action` references. |

### `TransactionPageDefinition`

| Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- |
| `page` | `NewPageConfig` | R | `pageKind` must be `transaction`; `dataSource` required. |
| `headerFields` | `FieldDef[]` | O | Header fields, unique within section. |
| `lineItems` | `TransactionLineItemsDef` | R | Line-entry definition. |
| `totalFields` | `FieldDef[]` | O | Total fields, unique within section. |
| `calculations` | `TransactionCalculationDef[]` | O | Derived values. |
| `documents` | `TransactionDocumentDef[]` | O | Host documents. |
| `posting` | `TransactionPostingDef` | O | Accounting-impacting posting declaration. |
| `importTemplate` | `ImportTemplateDefinition` | O | Import template. |
| `pageActions` | `ActionDef[]` | O | Standard page actions or `run_action` references. |
| `rowActions` | `ActionDef[]` | O | Standard row actions or `run_action` references. |

### Transaction line items

| Model | Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- | --- |
| `TransactionLineItemsDef` | `fieldId` | string | R | Non-blank collection field ID. |
|  | `label` | string | R | Non-blank. |
|  | `columns` | `FieldDef[]` | R | Non-empty; unique field IDs within line section. |
|  | `dataEntry` | `TransactionLineDataEntryDef` | O | Grid suggestions. |
| `TransactionLineDataEntryDef` | `mode` | string | O | If present, must be `grid`. |
|  | `suggestedMinRows` | integer | O | Non-negative. |
|  | `suggestedMaxRows` | integer | O | Non-negative and not below a positive minimum. |

### Transaction calculations

| Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- |
| `scope` | string | R | `header`, `line`, or `total`. |
| `kind` | string | R | `binary_op`, `formula`, or `sum`. |
| `targetFieldId` | string | R | Existing numeric field in the selected scope. |
| `inputFieldIds` | `string[]` | C | Exactly two numeric line-field IDs for `binary_op`. |
| `sourceFieldId` | string | C | Numeric line-field ID for `sum`. |
| `operator` | string | C | `+`, `-`, `*`, `/` for `binary_op`. |
| `expression` | `TransactionCalculationExpression` | C | Required for `formula`. |
| `precision` | integer | O | 0–8. |

`binary_op` must use line scope. `sum` must use total scope.

### `TransactionCalculationExpression`

| Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- |
| `kind` | string | R | `value`, `field`, `binary_op`, `sum`, `min`, `max`, `negate`, `coalesce`, or `if`. |
| `field` | string | C | Required for `field`; namespaced as `header.ID`, `line.ID`, or `totals.ID`. Unprefixed names use the current scope. Numeric references only. |
| `value` | number | C | Required for `value`. |
| `operator` | string | C | `+`, `-`, `*`, `/`; required for `binary_op`. |
| `args` | `TransactionCalculationExpression[]` | C | Exactly 2 for `binary_op`, exactly 1 for `negate`, at least 1 for `sum`, `min`, `max`, `coalesce`. Maximum nesting depth is 32. |
| `when` | `TransactionCalculationCondition` | C | Required for `if`. |
| `then` | `TransactionCalculationExpression` | C | Required for `if`. |
| `else` | `TransactionCalculationExpression` | C | Required for `if`. |

### `TransactionCalculationCondition`

| Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- |
| `field` | string | R | Existing value field reference in allowed scope; unlike expression fields, need not be numeric. |
| `operator` | string | R | `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `empty`, `not_empty`. |
| `value` | JSON | C | Required except for `empty` and `not_empty`. |

### Documents and transaction posting

| Model | Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- | --- |
| `TransactionDocumentDef` | `documentId` | string | R | Non-blank. |
|  | `name` | string | R | Non-blank. |
|  | `scope` | string | R | Currently `line`. |
|  | `filename` | string | O | Filename pattern. |
|  | `title` | string | O | Document title. |
|  | `fields` | `TransactionDocumentField[]` | R | Non-empty. |
| `TransactionDocumentField` | `label` | string | R | Non-blank. |
|  | `source` | string | R | Existing header/line/total field reference available from line scope. |
|  | `format` | string | O | Display format. |
| `TransactionPostingDef` | `trigger` | string | R | Currently `confirm`. |
|  | `dateSource` | string | O | Existing header or totals value-field reference. |
|  | `entryNo` | string | O | Existing header or totals value-field reference. |
|  | `memo` | string | O | Posting memo. |
|  | `lines` | `TransactionPostingLine[]` | R | Non-empty. |
| `TransactionPostingLine` | `accountSource` | string | R | Existing header or totals value-field reference. |
|  | `description` | string | O | Line description. |
|  | `debit` | `TransactionCalculationExpression` | C | At least one of `debit` or `credit`. |
|  | `credit` | `TransactionCalculationExpression` | C | At least one of `debit` or `credit`. |

Posting is host-owned accounting behavior. A declaration may propose entries, but it does not bypass validation, permissions, period controls, review, audit history, or the canonical accounting workflows. Debits must equal credits; the GL remains the source of truth; corrections to posted history must use the company's permitted audit, reversal, void, supersede, or additive-correction path.

## `expand_page` definition

| Model | Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- | --- |
| `ExpandPageDefinition` | `targetPageId` | string | R | Non-blank target plugin page ID. |
|  | `addFields` | `FieldDef[]` | O | Added fields. |
|  | `pageActions` | `ActionOverrides` | R | Page action changes. |
|  | `rowActions` | `ActionOverrides` | R | Row action changes. |
| `ActionOverrides` | `add` | `ActionDef[]` | O | Added actions valid for scope. |
|  | `override` | `ActionDef[]` | O | Overridden actions valid for scope. |

## `accounting_schedule` definition

| Model | Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- | --- |
| `AccountingScheduleDefinition` | `schedule` | `AccountingScheduleConfig` | R | Schedule metadata. |
|  | `definitionVersion` | string | O/C | Set to `"2"` for public runtime schedules; legacy omission remains install-compatible. |
|  | `templates` | `AccountingScheduleTemplateDef[]` | O | Schedule templates. |
|  | `fields` | `FieldDef[]` | O | Unique field IDs. |
|  | `relationRoles` | `AccountingScheduleRelationRoleDef[]` | O | Unique relation role IDs. |
|  | `accountRoles` | `AccountingScheduleAccountRoleDef[]` | O/C | Posting line role IDs must resolve here. |
|  | `calculation` | `AccountingScheduleCalculationDef` | R | Schedule calculation inputs. |
|  | `posting` | `AccountingSchedulePostingDef` | R | Host posting proposal. |

### Schedule metadata and templates

| Model | Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- | --- |
| `AccountingScheduleConfig` | `scheduleId` | string | R | Non-blank. |
|  | `title` | string | R | Non-blank. |
|  | `description` | string | O | Description. |
|  | `icon` | string | O | Host icon. |
|  | `category` | string | O | Category. |
|  | `route` | string | O | Route. |
| `AccountingScheduleTemplateDef` | `templateId` | string | R | Non-blank. |
|  | `name` | string | R | Non-blank. |
|  | `description` | string | O | Description. |
|  | `calculationMethod` | string | O | Method default. |
|  | `postingFrequency` | string | O | Frequency default. |
|  | `roundingPolicy` | string | O | Rounding policy. |
|  | `accountMappings` | `Record<string, string>` | O | Keys must reference declared account-role IDs. |
|  | `dimensionMappings` | `Record<string, string>` | O | Dimension mappings. |
|  | `headerDefaults` | JSON | O | Default header payload. |
|  | `requireApproval` | boolean | O | Approval marker. |

### Schedule roles, calculation, and posting

| Model | Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- | --- |
| `AccountingScheduleRelationRoleDef` | `roleId` | string | R | Non-blank; unique. |
|  | `label` | string | R | Non-blank. |
|  | `targetEntityType` | string | R | Non-blank. |
|  | `cardinality` | string | O | `one` or `many`. |
|  | `required` | boolean | O | Required relation. |
|  | `displayPolicy` | string | O | Host display policy. |
|  | `allowedSourcePageIds` | `string[]` | O | Allowed source pages. |
| `AccountingScheduleAccountRoleDef` | `roleId` | string | R | Non-blank; unique. |
|  | `label` | string | R | Non-blank. |
|  | `required` | boolean | O | Required mapping. |
|  | `accountTypes` | `string[]` | O | Allowed account types. |
| `AccountingScheduleCalculationDef` | `methods` | `string[]` | O | If non-empty, must contain `defaultMethod`. |
|  | `defaultMethod` | string | R | Non-blank. |
|  | `amountSource` | string | R | Non-blank. |
|  | `startDateSource` | string | R | Non-blank. |
|  | `endDateSource` | string | C | At least one of this, `usefulLifeMonthsSource`, `usefulLifeYearsSource`. |
|  | `usefulLifeMonthsSource` | string | C | Same conditional rule. |
|  | `usefulLifeYearsSource` | string | C | Same conditional rule. |
|  | `periodCountSource` | string | C | Required by v2; references a declared number field. |
|  | `salvageValueSource` | string | O | Salvage-value source. |
|  | `openingRecognizedAmountSource` | string | O/C | Required by v2; references a declared currency or number field. |
|  | `openingRecognizedThroughSource` | string | O/C | Required by v2; references a declared date field. |
|  | `postingConvention` | string | O/C | Required by v2; currently `month_end`. |
|  | `frequency` | string | O | Calculation frequency. |
|  | `roundingPolicy` | string | O | Rounding policy. |
| `AccountingSchedulePostingDef` | `mode` | string | O | Posting mode. |
|  | `dateSource` | string | O | Posting date source. |
|  | `entryNoPattern` | string | O | Entry-number pattern. |
|  | `memoPattern` | string | O | Memo pattern. |
|  | `idempotencyKeyPattern` | string | O | Idempotency pattern. |
|  | `lines` | `AccountingSchedulePostingLine[]` | R | Non-empty. |
| `AccountingSchedulePostingLine` | `accountRoleId` | string | R | Must reference declared account role. |
|  | `description` | string | O | Description. |
|  | `debit` | string | C | At least one of `debit` or `credit` non-blank. |
|  | `credit` | string | C | Same. |

Schedule posting is subject to the same host-owned accounting constraints stated for transaction posting.
V2 schedules also declare a required string field named `sourceReference` and
both accounting capabilities. The host owns journal preview, exact-hash commit,
idempotency, period controls, audit history, and reversals.

The host derives CSV/XLSX import columns from `fields[].fieldId` and
`accountRoles[].roleId`; there is no schedule `importTemplate` manifest field.
Only the first XLSX worksheet is read. Account cells accept an exact company
account ID or a unique company account code and must pass active, posting, and
declared account-type checks. Import preview is limited to 500 rows, and exact
preview-hash commit atomically creates drafts with idempotent `importKey`
replay. Schedule import does not post journals.

## `report` definition

New executable reports set optional `definitionVersion: "2"` while retaining
the additive `report`, `data`, `views`, and `customization` shape below. The
runtime does not accept top-level source/query/table fields or parameters.
Only table views should be authored. See [Native Custom Reports](native-custom-reports.md)
for routes, examples, limits, errors, saved views, and optional SPRKQL tooling.

### Enums

| Type | Allowed values |
| --- | --- |
| `ReportBasisKind` | `ledger_posted_accrual`, `ledger_cash_basis`, `source_document`, `bank_evidence`, `plugin_resource`, `forecast`, `reconciliation` |
| `ReportAmountMode` | `base_currency`, `transaction_currency`, `reporting_currency`, `none` |
| `ReportPostingState` | `all`, `draft`, `issued_or_posted`, `posted`, `open`, `paid`, `non_posting` |
| `ReportFilterOperator` | `eq`, `ne`, `in`, `not_in`, `contains`, `gt`, `gte`, `lt`, `lte`, `between`, `is_empty`, `is_not_empty` |
| `ReportAggregateFunction` | `sum`, `count`, `count_distinct`, `avg`, `min`, `max` |
| `ReportViewKind` | `table`, `pivot`, `chart` |

### Report models

| Model | Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- | --- |
| `ReportDefinition` | `definitionVersion` | string | O | If present, exactly `"2"`. |
| `ReportDefinition` | `report` | `ReportConfig` | R | Report metadata. |
|  | `data` | `ReportDataDefinition` | R | Catalog-backed data contract. |
|  | `views` | `ReportViewDefinition[]` | R | Non-empty. New reports must include a table view; pivot/chart values remain parser-compatibility enums and are not executable in the new runtime. |
|  | `customization` | `ReportCustomizationDefinition` | O | User customization. |
| `ReportConfig` | `reportId` | string | R | Non-blank. |
|  | `title` | string | R | Non-blank. |
|  | `category` | string | O | Category. |
|  | `description` | string | O | Description. |
|  | `icon` | string | O | Host icon. |
| `ReportBasisDefinition` | `kind` | `ReportBasisKind` | R | Must be accepted by selected source. |
|  | `dateField` | string | O | Catalog field of type `date` or `datetime`. |
|  | `amountMode` | `ReportAmountMode` | O | Closed enum. |
|  | `postingState` | `ReportPostingState` | O | Closed enum. |
| `ReportDataDefinition` | `source` | string | R | Current sources: `gl.lines`, `invoice.lines`, `bank.register`. |
|  | `grain` | string | O | If present must equal source grain. |
|  | `basis` | `ReportBasisDefinition` | R | Reporting basis. |
|  | `requiredFilters` | `ReportFilterDefinition[]` | O | Each needs `op`, and normally `value`. |
|  | `exposedFilters` | `ReportFilterDefinition[]` | O | Each needs non-empty `ops`. |
|  | `allowedGroupBy` | `string[]` | O | Catalog fields marked groupable. |
|  | `measures` | `ReportMeasureDefinition[]` | O | Unique measure IDs. |
|  | `defaultSort` | `ReportSortDefinition[]` | O | Sortable catalog fields or declared measure IDs. |
| `ReportFilterDefinition` | `field` | string | R | Catalog field marked filterable. |
|  | `label` | string | O | Display label. |
|  | `op` | `ReportFilterOperator` | C | Required for `requiredFilters`; must be allowed for field. |
|  | `value` | JSON | C | Required for required filters except `is_empty`/`is_not_empty`. |
|  | `ops` | `ReportFilterOperator[]` | C | Required for exposed filters; each allowed for field. |
|  | `default` | JSON | O | Default exposed value. |
| `ReportMeasureDefinition` | `measureId` | string | R | Non-blank; unique. |
|  | `field` | string | R | Catalog field with requested aggregate allowed. |
|  | `function` | `ReportAggregateFunction` | R | Allowed by field. |
|  | `label` | string | O | Display label. |
| `ReportSortDefinition` | `field` | string | R | Sortable field or measure ID. |
|  | `direction` | string | O | `asc` or `desc`. |
| `ReportViewDefinition` | `viewId` | string | R | Non-blank; unique. |
|  | `kind` | `ReportViewKind` | R | Closed enum. |
|  | `label` | string | O | Display label. |
|  | `columns` | `string[]` | O/C | Fields or measures; for pivot, required and groupable fields only. |
|  | `groupBy` | `string[]` | O | Groupable catalog fields. |
|  | `rows` | `string[]` | C | Required for pivot; groupable fields. |
|  | `values` | `string[]` | C | Required for pivot; declared measure IDs. |
| `ReportCustomizationDefinition` | `allowUserFilters` | boolean | O | Allows user filters. |
|  | `allowUserGroupBy` | boolean | O | Allows group changes. |
|  | `allowSavedViews` | boolean | O | Allows saved views. |
|  | `maxGroupLevels` | integer | O | Non-negative. |

### Current shipped catalog summary

The current catalog version defines:

| Source | Grain | Accepted basis | Default date |
| --- | --- | --- | --- |
| `gl.lines` | `ledger_line` | `ledger_posted_accrual` | `entry.date` |
| `invoice.lines` | `invoice_line` | `source_document`, `forecast` | `invoice.date` |
| `bank.register` | `bank_transaction` | `bank_evidence`, `reconciliation` | `bank.date` |

Authors must inspect `GET /v1/plugin-sdk/report-sources` for the installed
host's exact source contract.
Field IDs, operators, grouping, sorting, aggregates, semantics, and availability
are catalog properties, not arbitrary author values.

Choosing another accepted basis does not make the runtime perform a cash-basis,
FX, posting-state, or date-field conversion. Authors may use only the semantics
actually implemented by the selected source adapter.

## `connector` definition

### `ConnectorDefinition` and API

| Model | Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- | --- |
| `ConnectorDefinition` | `authMethods` | `ConnectorAuthMethod[]` | R | Non-empty; unique auth method IDs. |
|  | `api` | `ConnectorAPI` | R | Approved provider API. |
| `ConnectorAPI` | `baseUrl` | string | R | Public HTTPS base URL using the external-host restrictions above. |
|  | `executionPolicy` | `ConnectorExecutionPolicy` | R | Complete timeout and retry policy. |
|  | `operations` | `ConnectorAPIOperation[]` | R | At least one; unique operation IDs. |
| `ConnectorAPIOperation` | `operationId` | string | R | Plugin identifier; unique. |
|  | `label` | string | R | Non-blank. |
|  | `method` | `PluginHTTPMethod` | R | Must be granted. |
|  | `path` | string | R | Must remain on exact HTTPS origin. |
|  | `query` | `Record<string, JSON>` | O | Keys non-empty/no CRLF; values non-empty. |
|  | `body` | JSON | O | Forbidden for GET. |
|  | `semantics` | string | O | `read` or `write`. |
|  | `retrySafe` | boolean | O | Required for retrying/paginating unsafe non-GET operations unless semantics is `read`. |
|  | `executionPolicy` | `ConnectorExecutionPolicy` | O | Complete per-operation override. |
|  | `connectionDiscovery` | `ConnectorSafeOutput` | O | At most one operation across connector may declare this. Discovery operations cannot be called by `api.execute` action steps. |
|  | `variables` | `ConnectorOperationVariable[]` | O | Approved host-provided values. |
|  | `pagination` | `ConnectorCursorPagination` | O | Cursor pagination. |
|  | `authMethodIds` | `string[]` | O/C | Unique references to declared auth methods; secret-bearing variables require exactly one. |

### Connector authentication union

`ConnectorAuthMethod.type` selects the allowed/required subordinate fields.

| Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- |
| `authMethodId` | string | R | Plugin identifier; unique. |
| `label` | string | R | Non-blank. |
| `type` | string | R | `api_key`, `client_keys`, `oauth2_pkce`, or `hosted_token_exchange`. |
| `credentialFields` | `ConnectorCredentialField[]` | C | Required for API key/client keys/hosted exchange; OAuth fields allowed for client ID/secret. |
| `injections` | `ConnectorCredentialInjection[]` | C | Required for API key/client keys; forbidden for OAuth/hosted exchange. |
| `oauth2` | `ConnectorOAuth2PKCE` | C | Required only for `oauth2_pkce`. |
| `hostedAuthorization` | `ConnectorHostedAuthorization` | C | Required only for `hosted_token_exchange`. |

### Credential fields and injections

| Model | Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- | --- |
| `ConnectorCredentialField` | `key` | string | R | Plugin identifier; unique per auth method; username/password-like keys forbidden. |
|  | `label` | string | R | Non-blank. |
|  | `kind` | string | R | `api_key`, `client_id`, `client_secret`, subject to auth type. |
|  | `required` | boolean | R | Must be true. |
| `ConnectorCredentialInjection` | `credentialKey` | string | R | References a credential field; each required credential must be injected; no duplicate key. |
|  | `in` | string | R | `header` or `json_body`. |
|  | `name` | string | C | Allowed request header name for header injection. |
|  | `path` | string | C | Dot-separated field path for JSON-body injection. |
|  | `prefix` | string | O | Header-only; maximum 64 bytes, no control characters. |

`api_key` requires exactly one `api_key` field. `client_keys` requires exactly one `client_id`, one `client_secret`, and may include additional `api_key` fields.

### `ConnectorOAuth2PKCE`

| Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- |
| `authorizationUrl` | string | R | Public HTTPS URL. |
| `tokenUrl` | string | R | Public HTTPS URL. |
| `revocationUrl` | string | O | Public HTTPS URL. |
| `clientId` | string | C | Exactly one of `clientId` or `clientIdCredentialKey`; bounded/no controls. |
| `clientIdCredentialKey` | string | C | References a `client_id` credential. |
| `clientSecretCredentialKey` | string | C | References a `client_secret`; required for secret-based token auth. |
| `tokenAuthMethod` | string | O | Defaults to `none`; `none`, `client_secret_basic`, or `client_secret_post`. |
| `scopes` | `string[]` | O | Trimmed, non-empty, no control characters. |

### Hosted authorization

| Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- |
| `startOperationId` | string | R | Plugin identifier referencing an operation authorized for this auth method. |
| `launchUrlPath` | string | R | Dot-separated output field path. |
| `allowedLaunchOrigins` | `string[]` | R | 1–8 exact public HTTPS origins. |
| `sessionOutputs` | `Record<string, string>` | O | Plugin-identifier keys to field paths. |
| `statusOperationId` | string | R | Authorized operation reference. |
| `completionOutputs` | `Record<string, string>` | R | Non-empty; plugin-identifier keys to field paths. |
| `exchangeOperationId` | string | R | Authorized operation reference. |
| `credentialOutputs` | `Record<string, string>` | R | Non-empty; plugin-identifier keys to field paths written to vault. |
| `sessionTtlSeconds` | integer | O | If nonzero, 60–1800. |

### Operation variables

| Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- |
| `source` | string | R | `credential`, `authorization_session`, `authorization_output`, `context`, or `configuration`. |
| `key` | string | R | Must resolve in source. Context keys: `companyId`, `connectionId`, `bindingId`, `sourceItemId`, `targetId`; configuration keys are plugin identifiers. |
| `in` | string | R | `header`, `query`, or `json_body`. Secret-bearing sources cannot enter query. |
| `name` | string | C | Allowed header name or non-blank query name. |
| `path` | string | C | Dot-separated path for JSON body. |
| `prefix` | string | O | Header-only; ≤64 bytes and no controls. |
| `omitWhenEmpty` | boolean | O | Omit unresolved/empty value. |

### Pagination and execution policy

| Model | Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- | --- |
| `ConnectorCursorPagination` | `requestIn` | string | R | `query` or `json_body`; GET requires query. |
|  | `requestName` | string | C | Required for query; forbidden for JSON body. |
|  | `requestPath` | string | C | Required field path for JSON body; forbidden for query. |
|  | `omitWhenEmpty` | boolean | O | Omit initial empty cursor. |
|  | `nextCursorPath` | string | R | Dot-separated response path. |
|  | `hasMorePath` | string | R | Dot-separated response path. |
|  | `stateResource` | `ConnectorResourceRef` | R | Must resolve bundle-wide to `host_only` records with required string `cursor`. |
|  | `scope` | string | R | `connection` or `binding`. |
|  | `maxPages` | integer | R | 1–100. |
|  | `maxItems` | integer | R | 1–100000. |
| `ConnectorResourceRef` | `extensionId` | string | R | Plugin identifier. |
|  | `resourceId` | string | R | Plugin identifier. |
| `ConnectorExecutionPolicy` | `attemptTimeoutMs` | integer | R | 100–60000. |
|  | `totalTimeoutMs` | integer | R | At least attempt timeout; ≤120000. |
|  | `retry` | `ConnectorRetryPolicy` | R | Retry contract. |
| `ConnectorRetryPolicy` | `maxAttempts` | integer | R | 1–3. |
|  | `initialBackoffMs` | integer | R | 0–10000. |
|  | `maxBackoffMs` | integer | R | At least initial; ≤10000. |
|  | `retryOn` | `ConnectorRetryCondition[]` | C | Required when attempts >1; unique values from `connection_error`, `timeout`, `408`, `429`, `500`, `502`, `503`, `504`. |

### Connection-discovery safe output

| Model | Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- | --- |
| `ConnectorSafeOutput` | `accountsPath` | string | R | `$` or dot-separated path. |
|  | `fields` | `ConnectorSafeAccountFieldMap` | R | Canonical account mappings. |
| `ConnectorSafeAccountFieldMap` | `externalAccountId` | string | R | Dot-separated field path. |
|  | `displayName` | string | R | Dot-separated field path. |
|  | `institutionName` | string | O | Dot-separated field path. |
|  | `mask` | string | O | Dot-separated field path. |
|  | `type` | string | O | Dot-separated field path. |
|  | `subtype` | string | O | Dot-separated field path. |
|  | `currencyCode` | string | O | Dot-separated field path. |

## `actions` definition

### Action graph and inputs

| Model | Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- | --- |
| `ActionsDefinition` | `fieldMappings` | `ActionFieldMapping[]` | O | 1–32 when present; required only when referenced by `review.propose`. |
|  | `actions` | `ActionDefinition[]` | R | 1–32 actions. |
| `ActionDefinition` | `actionId` | string | R | Plugin identifier; unique. |
|  | `label` | string | R | Non-blank. |
|  | `trigger` | `PluginActionTrigger` | R | `manual`. |
|  | `binding` | `ActionBinding` | O | Requires binding capability; bound API steps share connector resource. |
|  | `inputs` | `ActionInput[]` | O | Unique input IDs. |
|  | `steps` | `ActionStep[]` | R | 1–16, unique step IDs. |
| `ActionBinding` | `sourceCollection` | `PluginBindingSourceCollection` | R | Closed enum. |
|  | `targetType` | `PluginBindingTargetType` | R | Closed enum and granted target. |
| `ActionInput` | `inputId` | string | R | Plugin identifier; unique. |
|  | `label` | string | R | Non-blank. |
|  | `description` | string | O | Description. |
|  | `type` | string | R | `text`, `textarea`, `number`, `boolean`, `date`, `date_range`, `money`, `select`, `multi_select`, `reference`, `dimension_assignments`. |
|  | `required` | boolean | O | Required input. |
|  | `multiple` | boolean | O | Canonical for multi-select and multi-reference; at most 100 values. |
|  | `options` | `ActionInputOption[]` | C | Non-empty for select/multi-select; forbidden otherwise. |
|  | `reference` | `ActionInputReference` | C | Required only for reference; native or same-plugin records. |
|  | `defaultValue` | JSON | O | Must match the exact runtime shape documented in [Manual Plugin Workflows](manual-plugin-workflows.md). Null is invalid. |
| `ActionInputOption` | `label` | string | R | Non-blank. |
|  | `value` | string | R | Non-blank. |
| `ActionStep` | `id` | string | R | Plugin identifier; unique. |
|  | `command` | string | R | `data.list`, `data.get`, `data.resolve`, `api.execute`, `review.import`, `review.propose`, or compatibility-only `resource.apply_delta`. |
|  | `with` | command-specific object | R | Strictly decoded: unknown fields are rejected. |

`resource.apply_delta` remains valid for existing schema-v2 plugins. New provider synchronization should use reviewed `review.propose` snapshot mappings so users can confirm creates, updates, and inactivations before persistence.

### Data-step `with`: `ActionDataStep`

| Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- |
| `entity` | string | R | `accounts`, `customers`, `items`, `vendors`; matching data capability required. |
| `id` | string | O | Identifier expression for get/resolve use. |
| `ids` | string | O | Identifier-list expression. |
| `limit` | integer | O | Result limit. |

### API-step `with`: `ActionAPIExecuteStep`

| Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- |
| `connector` | `ActionConnectorRef` | R | Connector operation; discovery operations unavailable here. |
| `connectionId` | string | R | Exactly `$context.connectionId`. |
| `requestBindings` | `ActionRequestBinding[]` | O | Bounded context/input/configuration/prior-step bindings. |
| `safeOutputs` | `ActionSafeOutput[]` | R | 1–8 normalized output collections. |

| Model | Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- | --- |
| `ActionConnectorRef` | `extensionId` | string | R | Connector extension identifier. |
|  | `resourceId` | string | R | Connector resource identifier. |
|  | `operationId` | string | R | Non-discovery connector operation identifier. |
| `ActionRequestBinding` | `source` | string | R | Pattern `$context.*`, `$inputs.*`, `$configuration.*`, or `$steps.*`; configuration field must exist. |
|  | `in` | string | R | `query` or `json_body`. |
|  | `name` | string | C | Required for query; forbidden for JSON body. |
|  | `path` | string | C | Field path required for JSON body; forbidden for query. |
| `ActionSafeOutput` | `collection` | string | R | Plugin identifier; unique within step. |
|  | `itemsPath` | string | R | `$` or dot-separated field path. |
|  | `maxItems` | integer | R | 1–10000. |
|  | `fields` | `Record<string, ActionSafeOutputField>` | R | Non-empty; keys are plugin identifiers. |
| `ActionSafeOutputField` | `path` | string | R | `$` or dot-separated field path. |
|  | `type` | `DataType` | R | Closed enum. |
|  | `required` | boolean | O | Required normalized field. |

### Review-proposal definitions and step

| Model | Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- | --- |
| `ActionFieldMapping` | `mappingId` | string | R | Unique within the actions extension. |
|  | `source` | `ActionProposalSource` | R | `plugin_selection` resource reference or earlier `safe_output` path. |
|  | `target` | `ActionProposalTarget` | R | Native create/create-or-link/create-draft or plugin-resource snapshot sync. |
|  | `fields` | `Record<string, ActionFieldMappingValue>` | R | Non-empty target-to-source/literal mapping. |
|  | `writeback` | `ActionProposalWriteback` | O | Plugin-selection source only; records target ID and optional result operation. |
|  | `delta` | `ActionProposalDelta` | C | Required only for plugin-resource `sync_snapshot`. |
| `ActionFieldMappingValue` | `from` | string | C | Exactly one of `from` or `value`; declared source field ID. |
|  | `value` | string/number/boolean | C | Exactly one of `from` or `value`; bounded literal. |
| `ActionReviewProposeStep.with` | `mappingId` | string | R | Referenced field mapping; `review.propose` must be terminal. |
| `ActionProposalWriteback` | `targetIdField` | string | R | Declared source-resource field receiving the canonical target ID. |
|  | `operationField` | string | O | Declared source-resource field receiving the result operation. |
| `ActionProposalDelta` | `mode` | string | R | `full_snapshot`. |
|  | `identityField` | string | R | Declared target identity field. |
|  | `missing` | string | R | `mark_inactive`. |
|  | `inactiveField` | string | R | Declared target boolean field. |

Native target combinations are accounts/vendors/items `create`, customers
`create_or_link`, invoices/bills `create_draft`, and journal entries `post`. A plugin-resource target uses
`sync_snapshot` and a same-plugin records resource. See
[Reviewed Record Proposals](reviewed-record-proposals.md).

### Review-import `with`: `ActionReviewImportStep`

`review.import` must be the final action step. It stages data for the host's native review workflow; it is not a direct core-record write.

| Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- |
| `targetEntity` | string | R | `bank_register`, `accounts`, `customers`, `vendors`, or `items`; matching review grant required. |
| `target` | `Record<string, string>` | R | For `bank_register`, `accountId` must equal `$context.targetId`; for a master-data target, use `{}`. |
| `source` | string | R | Earlier `$steps.STEP.safeOutput.COLLECTION`. |
| `fields` | `Record<string, string>` | R | Target field to safe-output field. The target-specific canonical keys and types are defined in [Native Import Reviews](native-import-reviews.md). Required targets must map to required compatible safe outputs. |
| `transforms` | `ActionReviewTransforms` | O | Bank-register review transformations only. |
| `ActionReviewTransforms.amount` | `ActionNumberTransform` | O | Amount transform. |
| `ActionNumberTransform.multiply` | number | R | Finite, nonzero, absolute value ≤1,000,000. |

## `workflow` definition additions

The complete workflow command and expression contract is documented in
[Manual Plugin Workflows](manual-plugin-workflows.md). The fields below cover
host-staged file inputs and grouped journal proposals added to the public
authoring contract.

### Manual workflow file input

| Model | Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- | --- |
| `WorkflowFileInput` | `inputId` | string | R | Plugin identifier; unique among workflow inputs. |
|  | `label` | string | R | Non-blank. |
|  | `description` | string | O | User-facing guidance. |
|  | `type` | string | R | Exactly `file`; manual workflows only. |
|  | `required` | boolean | O | Must be true when used by `dataset.read`. |
|  | `file` | `WorkflowFileSpec` | R | Staging and normalized-row contract. |
| `WorkflowFileSpec` | `formats` | string[] | R | One or both of `csv`, `xlsx`; every format needs a matching `files.ingest` grant. |
|  | `maxBytes` | integer | O | 1–5,242,880. |
|  | `maxRows` | integer | O | 1–500. |
|  | `fields` | `WorkflowFileField[]` | R | 1–128 declared normalized fields. |
| `WorkflowFileField` | `fieldId` | string | R | Plugin identifier; unique and not host-reserved. |
|  | `label` | string | R | Non-blank canonical header label. |
|  | `aliases` | string[] | O | At most 16 unique non-blank header aliases. Normalized IDs, labels, and aliases cannot ambiguously name two fields. |
|  | `dataType` | `DataType` | R | Normalized runtime value type. |
|  | `required` | boolean | O | Every accepted row must contain a value when true. |
| `WorkflowDatasetReadCommand.with` | `inputId` | string | R | Declared required file input. |
|  | `limit` | integer | O | 1–500 and at least the file's declared `maxRows`. |

The workflow receives `{datasetRef, contentHash}`, never raw bytes or a local
path. Submitted normalized and derived rows become durable workflow audit
evidence.

### Journal preview shapes and deduplication

| Model | Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- | --- |
| `WorkflowJournalPreviewWith` | `source` | string | R | Earlier reviewed collection. |
|  | `shape` | string | O/C | Omitted or `entries` for fixed entries; required as `line_records` for grouped source rows. |
|  | `title` | string | O | At most 160 characters. |
|  | `entry` | `WorkflowJournalEntry` or `WorkflowJournalLineRecordEntry` | R | Shape-specific entry template. |
|  | `deduplication` | `WorkflowJournalDeduplication` | O | Requires an explicit entry `sourceRecordId`. Available for either shape. |
| `WorkflowJournalLineRecordEntry` | `entryKey` | `WorkflowExpression` | R | Stable grouping value shared by all rows for one journal. |
|  | `date` | `WorkflowExpression` | R | Identical resolved header value across grouped rows. |
|  | `sourceRecordId` | `WorkflowExpression` | R | Stable economic identity, identical across grouped rows. |
|  | `entryNo`, `memo`, `vendorId` | `WorkflowExpression` | O | Must resolve identically across grouped rows. |
|  | `line` | `WorkflowJournalLineRecord` | R | Converts each reviewed source row to one journal line. |
| `WorkflowJournalLineRecord` | `accountId` | `WorkflowExpression` | R | Active posting account resolved by the host. |
|  | `debit` | `WorkflowExpression` | C | At least one of debit or credit must be declared; both expressions may be declared. Runtime requires exactly one positive side. |
|  | `credit` | `WorkflowExpression` | C | At least one of debit or credit must be declared; both expressions may be declared. Runtime requires exactly one positive side. |
|  | `description`, `dimensionAssignments` | `WorkflowExpression` | O | Host-validated optional line fields. |
| `WorkflowJournalDeduplication` | `mode` | string | R | Exactly `source_record`. |
|  | `onChange` | string | R | Exactly `correction_required`; changed posted history is never silently replaced. |

Fixed `entries` templates continue to use `entry.lines[]`, where each declared
line has exactly one of `debit` or `credit`. Grouped `line_records` is the only
shape that permits both expressions on its single row-level `entry.line`.

## `plugin_configuration` definition

Only one configuration extension is allowed per bundle. It must have exactly one `configuration` resource, be company-scoped, and cannot request direct network or secret access.

### Configuration root and discriminated sections

| Model | Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- | --- |
| `PluginConfigurationDefinition` | `title` | string | R | 1–160 characters after trim. |
|  | `description` | string | O | ≤4000 characters. |
|  | `sections` | `PluginConfigurationSection[]` | R | 1–32; unique section IDs. |
| `PluginConfigurationSection` | `sectionId` | string | R | Plugin identifier; unique. |
|  | `kind` | string | R | `fields`, `connection`, or `bindings`. |
|  | `title` | string | R | 1–160 characters. |
|  | `description` | string | O | ≤4000 characters. |
|  | `fields` | `PluginConfigurationField[]` | C | Required/non-empty only for `fields`; at most 128 fields bundle-wide. |
|  | `connection` | `PluginConfigurationConnectionSection` | C | Required only for `connection`. |
|  | `bindings` | `PluginConfigurationBindingsSection` | C | Required only for `bindings`. |

### Configuration fields

| Model | Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- | --- |
| `PluginConfigurationField` | `fieldId` | string | R | Plugin identifier; unique bundle-wide. |
|  | `label` | string | R | 1–160 characters. |
|  | `type` | string | R | `text`, `textarea`, `number`, `boolean`, `select`. |
|  | `required` | boolean | R | Required value. |
|  | `description` | string | O | ≤2000 characters. |
|  | `defaultValue` | string/number/boolean | O | Type-matched: text ≤16 KiB/no controls; textarea ≤64 KiB with tabs/newlines allowed; finite number; boolean; or declared select string. JSON null is treated as absent. |
|  | `options` | `PluginConfigurationOption[]` | C | Select only; 1–100. Forbidden otherwise. |
| `PluginConfigurationOption` | `value` | string | R | 1–256, already trimmed, no controls, unique within field. |
|  | `label` | string | R | 1–160 characters. |

### Connection and binding sections

| Model | Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- | --- |
| `PluginConfigurationConnectorRef` | `extensionId` | string | R | Existing connector extension. |
|  | `resourceId` | string | R | Its connector resource. A connector resource cannot be referenced by two configuration sections. |
| `PluginConfigurationConnectionSection` | `connector` | `PluginConfigurationConnectorRef` | R | Connector reference. |
|  | `required` | boolean | R | Connection requiredness. |
|  | `allowMultiple` | boolean | O | Multiple connection instances. |
|  | `actions` | `PluginConfigurationConnectionAction[]` | R | 1–16; unique action IDs. |
| `PluginConfigurationConnectionAction` | `actionId` | string | R | Plugin identifier; unique within section. |
|  | `kind` | string | R | `configure_credentials`, `authorize_oauth2`, `authorize_hosted`, `discover_connection`. |
|  | `label` | string | R | 1–160 characters. |
|  | `authMethodId` | string | C | Required for the three authorization/configuration kinds; references matching auth type; forbidden for discovery. |
|  | `operationId` | string | C | Required only for discovery; must reference operation with `connectionDiscovery`. |
| `PluginConfigurationBindingsSection` | `connectionSectionId` | string | R | Existing connection section. |
|  | `sourceCollection` | `PluginBindingSourceCollection` | R | Currently bundle contract supports only `accounts` for connector discovery bindings. |
|  | `targetType` | `PluginBindingTargetType` | R | Must be granted by binding capability. |
|  | `required` | boolean | O | Binding requiredness. |
|  | `sourceLabel` | string | O | ≤160 characters. |
|  | `targetLabel` | string | O | ≤160 characters. |

## `existing_page_actions` definition

| Model | Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- | --- |
| `ExistingPageActionsDefinition` | `targetPageKey` | string | R | One of the granted surfaces: `banking.import.source.actions`, `chart`, `customers`, `vendors`, or `items`. |
|  | `actions` | `ExistingPageActionDef[]` | R | Non-empty; unique action IDs. |
| `ExistingPageActionDef` | `actionId` | string | R | Non-blank; unique. |
|  | `label` | string | R | Non-blank. |
|  | `kind` | string | R | Must be `run_action`. |
|  | `action` | `ExistingPageActionAction` | R | Manual action reference. |

| Model | Field | JSON type | Req. | Constraints |
| --- | --- | --- | --- | --- |
| `ExistingPageActionAction` | `extensionId` | string | R | Existing `actions` extension. |
|  | `actionId` | string | R | Existing manual action. |
|  | `inputs` | `ActionInput[]` | O | Input declarations supplied by the surface. |
|  | `requiresCandidate` | boolean | O | Requires a page candidate/context item. |

## Authoring cautions

1. Capability coverage is bundle-wide and validated after individual files parse.
2. Cross-extension references must resolve to the correct extension/resource/operation/action type.
3. `json.RawMessage` in the Go model does not mean arbitrary executable behavior; it means a JSON value whose constraints are described above, or an area where the current validator has not yet published a narrower author contract.
4. Connector credentials remain host-owned and write-only. Do not put secrets in manifests, configuration fields, query strings, logs, or safe outputs.
5. Plugins do not gain direct core-record or accounting write paths. Use native review and canonical posting workflows.
6. Use only the extension types and shapes documented here. Historical schema-v2 parser paths are not part of the new-plugin API.
