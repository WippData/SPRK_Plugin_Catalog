# Firm Chart of Accounts Starter

This schema-v2 plugin adds **Start from firm template** to the native Chart of
Accounts page. The user selects one small template, the plugin fetches typed
JSON rows, and `review.import` opens SPRK's normal account preview. The plugin
never creates an account directly and never posts to the ledger.

## Included template choices

- Professional services
- Retail and e-commerce
- Nonprofit

The versioned template service requires an account code and returns account
name, canonical type, type-compatible subtype, description, and narrowly
justified setup flags. The native account target still treats code as
company-conditionally required. Only
Accounts Receivable and Accounts Payable are proposed as control accounts.
Operating bank and credit-card accounts are proposed as reconcilable. All rows
remain user-confirmed in the native preview, where supported preview fields can
be edited and rows can be excluded, resolved as duplicates, or retried. Company
account-code requirements are enforced there. If the company's default AR or AP
setting is blank, confirming the proposed Accounts Receivable or Accounts
Payable control row can populate that default through SPRK's canonical account
creation path.

## Required service before release

The current schema-v2 action runner cannot embed rows, parse a bundled JSON
file, or use `$inputs` directly as `review.import` source. A connector safe
output is therefore required. Before catalog release, deploy this exact read-only
contract at the connector origin in `extensions/connector.json`:

```text
GET /v1/chart-of-accounts/templates/accounts?version=1.0.0&template=<template-id>
X-SPRK-Template-Key: <company connection credential>
```

Supported template IDs are `professional-services`, `retail-ecommerce`, and
`nonprofit`. A successful response is:

```json
{
  "accounts": [
    {
      "code": "1000",
      "name": "Operating Checking",
      "type": "Asset",
      "subtype": "Bank",
      "description": "Primary operating bank account.",
      "reconcileAccount": true,
      "isActive": true
    }
  ]
}
```

The service must reject unknown template/version values, return no more than
100 accounts, authenticate the access key, and keep published template versions
immutable. Every account must supply a non-empty `code`, `name`, and `type`.
The `endpoint-fixtures/` files are the version-1.0.0 response bodies.

## Validation

From the plugin catalog repository:

```bash
npm run validate:plugin -- firm-chart-of-accounts-starter
```

Local validation proves bundle structure and cross-extension references. The
exact ZIP must still pass SPRK Install Preview, and the service must be exercised
against a test company before release.
