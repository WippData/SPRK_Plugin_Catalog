# API Versioning for New Plugins

## Version fields

- Root and extension manifest `schemaVersion` is `"2"`.
- Plugin-owned resource `schemaVersion` is `1`.
- `pluginId` is permanent across releases.
- `version` identifies a plugin or extension release and must increase for upgrades.
- `runtime.minAppVersion` is the earliest SPRK version that implements every field
  and behavior the bundle requires.

## Stable contract keys

Treat every ID as persisted API surface: plugin, extension, resource, field,
page, action, step, input, operation, auth method, configuration section,
report, saved view, semantic source/version, measure, parameter, schedule,
template, relation role, and account role.

Change a label for presentation. Do not rename an ID for presentation.

For ReportDefinition v2, changing source version, accounting semantics,
governing date, grain, measure meaning, or a locked predicate can change report
meaning even when IDs remain stable. Publish a new report ID or an explicit
compatibility migration. The current runtime detects definition-digest
conflicts but does not automatically migrate or mark company-shared views
`needs_review`; preserve old fields or require the user to recreate the view.

## Backwards-compatible changes

- Add an optional field or configuration value.
- Add a new action, operation, optional report field or measure inside the
  existing safe customization envelope, or optional resource.
- Expand an enum only when every existing reader safely handles unknown/new values.
- Add a safe default without changing existing stored meaning.

## Changes requiring a migration design

- Making an optional field required.
- Removing or renaming any stable ID.
- Changing a persisted field's type, units, sign, date meaning, or identity semantics.
- Changing connector output paths consumed by actions or bindings.
- Changing accounting calculations, account roles, posting timing, or idempotency keys.
- Removing data needed to explain an import, review, posting, reversal, or audit trail.

## Documentation update rule

Any new field, enum, discriminator branch, default, bound, reference rule, or
supported extension pattern must update:

1. [Typed Field Reference](schema-v2-field-reference.md);
2. [plugin-manifest.schema.json](plugin-manifest.schema.json);
3. the relevant recipe or starter example;
4. validation coverage and release notes.

CI should compare the documented schema against serialized SDK fields and fail
when they drift.
