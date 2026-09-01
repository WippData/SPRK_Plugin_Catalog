# Alternate Invoice Layout Demo

This uncataloged schema-v2 plugin is a capability proof for the
`document_template` extension. It contributes a **Modern Service Invoice**
print action while leaving SPRK's standard invoice layout unchanged.

The template is JSON-only. SPRK resolves the selected native invoice, renders
the declared blocks through the trusted host renderer, and opens the normal
interactive print/PDF preview.

The root manifest grants only `documents.render` for preview, PDF, and print.
The extension is company-scoped and targets the registered `invoices` source
at version `1`; its fields and table columns are limited to that source's
advertised contract. It does not change, post, or write back to the invoice or
general ledger.
