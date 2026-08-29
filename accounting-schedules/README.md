# Accounting Schedules

One plugin provides three separate company pages: **Fixed Assets**, **Prepaid Expenses**, and **Deferred Revenue**. Each page creates equal monthly recognition amounts, dates them at month-end, and assigns any rounding remainder to the final period.

Each schedule requires a source reference and account mappings constrained to the relevant account types. Opening recognized amount and recognized-through fields support bringing an existing schedule into SPRK without creating an opening journal entry.

The plugin proposes recognition entries only. SPRK owns preview, permission and period checks, balanced journal validation, exact proposal-hash commit, idempotency, audit history, and reversal or corrective workflows. The plugin never writes the GL or core accounting records directly.

## Page-specific accounting

- Fixed Assets: debit depreciation expense and credit accumulated depreciation. The fixed asset account is support-only and is never used by recognition posting lines.
- Prepaid Expenses: debit expense and credit the prepaid asset.
- Deferred Revenue: debit deferred revenue and credit revenue.

## Initial scope

This version is base-accounting-currency only and has no dimensions, FX, initial acquisition/payment/invoice entries, tax, disposal, impairment, daily calculations, or source-document relationship. `sourceReference` is descriptive provenance, not a native document link.

## Import examples

Each page supports host-reviewed CSV and XLSX import. The first row contains
declared schedule field IDs and account role IDs; for XLSX files, SPRK reads the
first worksheet. The examples in `templates/` use company account codes, which
are usually easier to prepare than internal account IDs.

SPRK stages every import for review. Account values resolve first by exact
company account ID, then by a unique company account code, and must identify an
active posting account of the type allowed by the role. Preview is limited to
500 rows. Commit is atomic and creates draft schedules only after the exact
preview hash is confirmed. Replaying the same `importKey` returns the prior
result instead of creating duplicates.

Import does not post recognition journals. Imported drafts use the same
Calculate, Activate, preview, and exact-hash posting controls as schedules
entered individually. The bundle does not require a connector, network access,
secrets, or a plugin file workflow.

This bundle is source-only until the matching host runtime contract is released. Do not catalog, publish, or distribute it independently.
