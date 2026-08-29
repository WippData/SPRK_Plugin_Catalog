# Payroll Journal Assistant

Payroll Journal Assistant imports line-oriented payroll general-ledger data,
joins each source category to a company-owned SPRK account mapping, and opens
the host's journal review. It never calculates payroll, plugs an imbalance,
posts automatically, or writes directly to the GL.

## Recommended Gusto path

Use Gusto's **General Ledger Mapper** payroll download. Gusto documents that the
mapper exports mapped payroll reports as CSV and can consolidate by project,
job, or department. Gusto does not publish a stable public list of every CSV
header, and third-party tag columns may change the shape. This plugin therefore
recognizes only cautious, declared header aliases and always shows host mapping
and review. It does not claim support for arbitrary Payroll Journal employee
detail exports.

Gusto's General Ledger report API documentation shows the row headers `Account
Type`, `Account Description`, optional `Job`, `Debit`, and `Credit`, with example
categories such as `RegularWages`, `EmployerTax`, `DebitNetPay`, and `DebitTax`.
The Gusto-shaped template uses those documented labels with fictional amounts;
it is not a promise that every General Ledger Mapper download has an identical
schema.

Official references:

- https://support.gusto.com/article/221020155120720/map-payroll-data-and-download-reports-with-the-general-ledger-mapper
- https://support.gusto.com/article/101334493100000/view-download-and-customize-reports-in-gusto-for-admins
- https://docs.gusto.com/embedded-payroll/docs/retrieve-a-general-ledger-report

Gusto reports payroll totals by check date. Use that check date as the posting
date unless the accountant deliberately chooses another valid accounting date.

## Setup and import

1. Add one active mapping for each unique combination of Profile, Source type,
   and Source description in the export. Matching uses normalized case and
   whitespace in the host; duplicate active keys are rejected by the join.
2. Choose an active posting SPRK account. `Expected side` is review guidance,
   not permission to reverse a source debit or credit.
3. From the page header, run **Import payroll journal**.
4. Choose Generic or Gusto, enter a stable payroll run ID, enter the check /
   posting date and memo, and upload a CSV or XLSX with no more than 500 lines.
5. Review every enriched line, then review the grouped journal. The host blocks
   missing accounts, rows with both/neither nonzero side, unbalanced entries,
   invalid dates/accounts, cutoff or hard-lock violations, and stale previews.
6. Commit only the exact reviewed hash.

The plugin groups all accepted lines under the entered payroll run ID into one
journal entry. It preserves source debits and credits. Job and Department remain
source evidence in v1; they are not silently converted into native dimensions.

## Accounting and corrections

Payroll clearing is usually preferable to posting source cash lines directly to
the bank account because the later provider debits can be matched without
duplicating payroll expense. This is guidance only; the accountant owns the
mapping and may choose another valid treatment.

Reusing the same profile and payroll run ID provides the journal's deduplication
identity. Source line IDs stabilize row evidence and review, but they are not
the journal entry identity. If a previously posted payroll source changes, the
host requires a correction workflow rather than silently replacing posted
history. Use the company's allowed reversal, void, supersede, or additive
adjustment path.

The workflow does not create payroll liabilities, infer gross-versus-net
treatment, convert employee-level payroll detail, map dimensions, or reconcile
provider bank withdrawals. Those decisions must remain explicit in the source
general-ledger report and account mappings.

## Privacy

Use company-level general-ledger lines. Do not upload employee PII or protected
benefit information. Raw file bytes are transient, but submitted normalized and
derived rows become durable workflow audit data and company-file evidence.

## Validate

From the catalog repository root:

```bash
python3 scripts/validate_plugin_folder.py payroll-journal-assistant
python3 -m unittest discover -s tests -p 'test*.py'
python3 scripts/catalog.py check
```
