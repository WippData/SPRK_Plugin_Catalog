# Invoice Sales Analysis

This schema-v2 plugin adds three separately discoverable native table reports:

- customer sales by invoice month;
- by item/SKU and line description, including source-unit quantity;
- by invoice month.

The reports lock `invoice.isActive = true` and invoice status to `open`, `partial`, or
`paid`. They aggregate only invoice-line amounts, line counts, and item/SKU-level
source-unit quantities. They never
aggregate invoice header totals or balances at line grain.

These reports intentionally differ from SPRK's native **Income by Customer** report. They
analyze source-document invoice sales mix and trends by invoice date. This is not a GL
income report, does not include manual or bank-linked income entries, and should not be
expected to reconcile directly to recognized income.

The default customer report is a customer-by-invoice-month trend, making it materially
different from the native GL-based Income by Customer report. The item/SKU report keeps
SKU and description together so blank or reused SKUs are not collapsed into one group.
Because the source does not expose unit of measure, quantity should be interpreted only
within each item/SKU and description group.

Each report allows up to two user-selected group levels and company-shared saved views.
