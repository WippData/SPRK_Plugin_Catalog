# Payroll journal templates

`generic-payroll-journal-lines.csv` is the canonical long-line format. Its
fictional sample balances to $10,800 of debits and credits. `Source line ID` is
recommended because it provides stable row evidence across re-exports; the
profile and payroll run ID provide the journal's deduplication identity.

`gusto-general-ledger-lines.csv` is a sanitized shape example, not a verbatim
customer export and not a promise that Gusto publishes a fixed General Ledger
Mapper CSV schema. Its category labels come from Gusto's public General Ledger
report example, while its company, job, and amounts are fictional. The workflow
declares cautious aliases for `Account Type` and `Account Description`; `Job`,
`Debit`, and `Credit` already match the canonical labels. Confirm the actual
headers and values in every download before submitting it. See
https://docs.gusto.com/embedded-payroll/docs/retrieve-a-general-ledger-report.

`payroll-account-mappings.csv` is a mapping-page import starter. Replace every
placeholder with an active posting account ID from the same SPRK company.

Never include Social Security numbers, bank-account numbers, pay rates, benefit
health information, or unrelated employee details. Submitted normalized rows
become workflow audit evidence even though the host does not retain original
file bytes.
