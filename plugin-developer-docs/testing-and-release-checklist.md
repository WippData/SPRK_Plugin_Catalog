# Testing and Release Checklist

Use all applicable gates. Static structure, backend acceptance, and runtime
exercise are separate validations.

## 1. Authoring review

- [ ] `manifest.json` is at the bundle root.
- [ ] Root and extension manifests use `schemaVersion: "2"`.
- [ ] Every referenced extension file exists and its declared `extensionId`
      matches the root reference.
- [ ] IDs are stable contract keys, not display labels.
- [ ] Capabilities are minimal and cover every declared operation and action
      step.
- [ ] No bundle file contains a credential, private key, token, or executable
      code.
- [ ] Every object, enum, and discriminator follows the typed field reference.
- [ ] Every persisted resource change is backwards compatible with existing
      records, or has an approved additive migration plan.

## 2. Authoritative application acceptance

Run the bundled dependency-free schema and bundle validator first:

```bash
npm run validate:plugin -- path/to/plugin-folder
```

It checks the fail-closed root and extension schemas, capabilities, resources,
hashes, action commands, connector references, safe outputs, review mappings,
binding context, and surface alignment. A nonzero exit means the bundle is not
ready to package.

For a v2 accounting schedule, also confirm every calculation source resolves
to a declared field of the expected type, `sourceReference` is required, both
accounting capabilities are granted, posting lines are balanced by design, and
only the host preview/commit path can affect the GL.

For schedule imports, test CSV and first-worksheet XLSX parsing, field-ID and
account-role headers, ID-before-unique-code account resolution, inactive or
non-posting and wrong-type account rejection, the 500-row cap, stale-hash
rejection, atomic draft creation, and idempotent `importKey` replay.

The authoritative external path is the SPRK install preview backed by the
backend SDK validators:

- [ ] Upload the exact ZIP intended for testing.
- [ ] Confirm the preview has no root-manifest, extension-manifest,
      bundle-contract, runtime-compatibility, or package errors.
- [ ] Resolve every preview warning before release.
- [ ] Confirm each requested capability is expected and understandable to the
      installer.
- [ ] Install only after the preview matches the intended plugin ID, publisher,
      version, extensions, and permissions.

The local validator is a fast authoring check and intentionally mirrors the
portable contract. The full release gate remains Install Preview using the
exact final ZIP because the application also applies its current runtime and
source-catalog rules.

Backend maintainers changing the contract should run focused plugin SDK/core
tests and then the repository gates:

```bash
go test ./internal/pluginsdk ./internal/core
go test ./...
go build ./...
```

## 3. Runtime test by company

- [ ] Enable the plugin for a test company.
- [ ] Confirm the expected page, configuration, connection, or contributed
      action is actually visible; installation alone is insufficient.
- [ ] Exercise empty, loading, success, validation-error, provider-error,
      timeout, retry, and disabled states.
- [ ] Verify one company's settings, connections, cursors, and records are not
      visible to another company.
- [ ] Disable the plugin and confirm execution stops without affecting normal
      app startup or unrelated features.

## 4. Connector and action tests

- [ ] Configure every auth method with test credentials through host UI.
- [ ] Confirm secrets cannot be read back through plugin configuration, runtime
      responses, or logs.
- [ ] Execute every declared HTTP operation and method.
- [ ] Verify paths cannot escape the HTTPS base host.
- [ ] Test timeout, bounded retry, provider `4xx`, provider `5xx`, malformed
      response, empty response, and output-over-limit behavior.
- [ ] Test every action input type and required/default behavior.
- [ ] Verify safe outputs contain only declared fields.
- [ ] For pagination, test first page, continuation, final page, item/page cap,
      and cursor recovery.
- [ ] For reviewed snapshots, test create, mapped-field update, unchanged,
      mark-inactive, reactivation, duplicate/blank identities, exclusion,
      cursor hold, and retry idempotency.
- [ ] For review imports, verify the selected target's required canonical
      mappings and compatible safe-output types. Confirm review is terminal and
      produces native staging rather than a direct core-record write.
- [ ] Confirm every review source is an earlier connector
      `$steps.<step>.safeOutput.<collection>`, never `$inputs`, pasted CSV, or a
      local file. Do not invent parser, transform, or validation commands.
- [ ] For proposals, test exact target grants, source authorization, source and
      target freshness, literal/from mapping values, one-row drawer routing,
      multi-row preview routing, accept/link/exclude decisions, provenance,
      writeback, cancellation, partial failure, and idempotent replay.
- [ ] Verify every invoice proposal is created as a draft and produces no
      journal, GL, or reconciliation change.
- [ ] For bank review, verify the accounts-to-accounts action binding and the
      selected candidate context. For master-data review, verify the action is
      unbound and the host selects only connected inventory for its declared
      connector.
- [ ] For master-data reviews, test edit, duplicate resolution, prerequisite
      mapping, exclusion, partial failure, and retry. The review must remain
      pending until every staged row is imported or intentionally excluded.
- [ ] Compare `accounts`, `customers`, `vendors`, and `items` field keys and
      types with `GET /v1/import-templates` and the owning page's download.

## 5. Report tests

- [ ] Grant every exact source ID/version with `reports.query` and grant catalog
      placement through `surfaces.contribute: ["reports.catalog.entries"]`.
- [ ] Confirm source, fields, operators, grouping, measures, sorting, basis,
      posting state, date semantics, and currency mode against
      `GET /v1/plugin-sdk/report-sources` for the minimum supported app version.
- [ ] Exercise detail and grouped tables, nested All/Any filters, typed values,
      deterministic sort/cursors, and empty results. Native record-link metadata
      is not part of the current plugin-report result contract.
- [ ] Prove user state cannot use undeclared fields, groups, measures, or
      operators or change source/accounting semantics.
- [ ] Test 100/500-row pagination, 20 columns, 20 filters, 3 groups, and
      predicate depth 4. Do not claim planned budgets or exports as shipped.
- [ ] Verify result metadata reports the source, source version, grain, basis,
      definition/query digests, row counts, and next cursor when present. Do not
      require planned duration, warning, or truncation metadata.
- [ ] Test company isolation, disabled/uninstalled plugin behavior, stale source
      versions, removed fields, saved-view digest conflicts, and retained views.
      Automatic `needs_review`/`unavailable` transitions are not shipped yet.
- [ ] Confirm header totals are not duplicated at line grain. Reconcile each
      advertised source to overlapping native behavior; do not claim AR/AP,
      payment, or other source coverage that is absent from discovery.
- [ ] Run `python3 -m unittest discover -s tests -p 'test*.py'` and structurally validate
      both report examples before packaging.

## 6. Manual workflow tests

- [ ] Launch with no selection, one selected row, multiple rows in different
      input order, and the 500-row boundary. Confirm the persisted resolved
      context always contains selection IDs, records, and count.
- [ ] Exercise every declared input type, default, required state, bounded
      option loading and local search, stale reference, wrong-company reference, account
      filter, duplicate multi-value, and 100-value boundary.
- [ ] Test filter, stable sort/null placement, distinct-first, strict numeric
      aggregates, unique-right join, null join keys, output cap, and `_workflow`
      source lineage.
- [ ] Exercise every if/switch branch and explicit stop status/message. Reject
      side effects inside branches, duplicate global IDs, forward sources,
      depth 4, more than 16 commands in a block, and more than 128 overall.
- [ ] Replay identical inputs and differently ordered selection IDs; confirm
      stable idempotency. Change inputs or selection and confirm a distinct run.
- [ ] Confirm review remains host-owned and a stale definition, target schema,
      selection, capability, company, disabled plugin, or unavailable resource
      fails closed.

## 7. Accounting-impacting tests

- [ ] Every generated posting balances debits and credits.
- [ ] Posting preserves native account validation, permissions, cutoff and
      hard-lock rules, reconciliation protections, and audit evidence.
- [ ] Duplicate execution does not create duplicate economic impact.
- [ ] Reversal, void, supersede, and additive correction remain linked to the
      original entry.
- [ ] Disabling and uninstalling the plugin do not remove posted history.
- [ ] Imported or suggested activity remains staged until accepted unless an
      explicit trusted host policy applies.
- [ ] Currency, rate, rate date, base amount, and FX treatment remain explicit
      when foreign currency is involved.

## 8. Upgrade and uninstall

- [ ] Disable the installed plugin before previewing an upgrade.
- [ ] Keep the same `pluginId` and use a strictly newer version.
- [ ] Test the upgrade using a company with existing configuration, connections,
      plugin records, and protected data.
- [ ] Confirm removed or renamed declarations do not strand data or break old
      records.
- [ ] Confirm the preview explains any re-enable requirement.
- [ ] Test uninstall with no data, live connections, plugin-owned data, and
      posted accounting history. Protected conditions must block destructive
      removal and state the reason.

## 9. Release artifact

- [ ] Build one deterministic ZIP with `manifest.json` at its root.
- [ ] Verify every declared extension SHA-256 against the exact packaged bytes.
- [ ] Re-run install preview using that exact ZIP.
- [ ] Record the plugin version, minimum app version, artifact SHA-256, and
      user-visible release notes.
- [ ] Do not rebuild or modify the ZIP after final validation.
