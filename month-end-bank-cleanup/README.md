# Month-End Bank Cleanup

This schema-v2 plugin adds three read-only native table reports:

- **Pending Bank Review** keeps the native `pending` status locked.
- **Unreconciled Confirmed Bank Activity** keeps `confirmed` and `reconciled = false` locked.
- **Bank Outflows Missing Vendor** keeps active, non-excluded outflows with an empty vendor locked.

The reports query `bank.register@1`. They do not assign vendors, confirm bank transactions,
match transactions, create journal entries, or change reconciliation state. Users return to
SPRK's native Banking workflow for those actions.

The host does not apply an automatic current-month period. Apply the **Bank date** filter for
the month-end period being reviewed.
