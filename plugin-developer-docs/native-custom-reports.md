# Native Custom Reports

SPRK report extensions declare safe tables over host-owned semantic sources.
The host validates and executes queries, renders results, applies company and
plugin authorization, and reports accounting context. Plugins never receive
SQL access, physical table names, unrestricted joins, or raw database access.

## Shipped report contract

The current product presents fixed, extension-authored reports. Accountants can run a
report and page through its results, but there is no end-user report builder: columns,
filters, grouping, measures, and sorting come from the extension definition.

The backend retains constrained view-state and saved-view groundwork as a potential
future report-builder use case. Those routes and definition fields are not a promise that
report-building controls are available in the current app. New catalog plugins should set
all `customization` flags to `false` and supply the complete report as an extension.

New report extensions set `definitionVersion: "2"` but use the existing
additive `report`, `data`, `views`, and `customization` fields. This is the
executable contract; top-level `source`, `query`, `table`, or parameter
declarations are not accepted.

The shipped developer catalog is:

```http
GET /v1/plugin-sdk/report-sources
```

It currently advertises exactly `gl.lines@1`, `invoice.lines@1`, and
`bank.register@1`. Only discovered source IDs, fields, operators, aggregates,
bases, and view features are supported. Broader ledger balances, AR/AP,
payments, checks, master-data, audit, and plugin-resource sources remain planned
until they appear in this endpoint.

The report execution path is:

```text
POST /v1/companies/:id/plugins/:pluginId/extensions/:extensionId/reports/:reportId/query
```

The backend also retains these dormant saved-view paths for possible future use:

```text
GET|POST /v1/companies/:id/report-views
PUT|DELETE /v1/companies/:id/report-views/:viewId
```

Field-options and plugin-report export routes are not part of the shipped
contract. Table output is the only supported new-report presentation; do not
author charts, dashboards, or pivots even though legacy parser enums remain.

## Capabilities

Grant each exact source and contribute to the report catalog through the
existing surface capability:

```json
{
  "reports.query": {
    "required": true,
    "sources": [{ "sourceId": "invoice.lines", "sourceVersion": "1" }]
  },
  "surfaces.contribute": {
    "required": true,
    "surfaces": ["reports.catalog.entries"]
  }
}
```

There is no wildcard, implicit latest version, same-plugin resource source, or
separate `reports.catalog.entries` root capability.

## Executable definition

```json
{
  "definitionVersion": "2",
  "report": {
    "reportId": "sales-by-customer",
    "title": "Sales by Customer",
    "category": "Sales"
  },
  "data": {
    "source": "invoice.lines",
    "grain": "invoice_line",
    "basis": {
      "kind": "source_document",
      "dateField": "invoice.date",
      "amountMode": "base_currency",
      "postingState": "issued_or_posted"
    },
    "exposedFilters": [
      { "field": "invoice.date", "label": "Invoice date", "ops": ["between", "gte", "lte"] },
      { "field": "customer.name", "label": "Customer", "ops": ["eq", "contains", "in"] }
    ],
    "allowedGroupBy": ["customer.name", "date.month"],
    "measures": [
      { "measureId": "sales_total", "field": "line.amount", "function": "sum", "label": "Sales" }
    ],
    "defaultSort": [{ "field": "customer.name", "direction": "asc" }]
  },
  "views": [
    {
      "viewId": "by-customer",
      "kind": "table",
      "columns": ["customer.name", "sales_total"],
      "groupBy": ["customer.name"]
    }
  ],
  "customization": {
    "allowUserFilters": false,
    "allowUserGroupBy": false,
    "allowSavedViews": false,
    "maxGroupLevels": 0
  }
}
```

`data.basis` must match a basis advertised by the selected source. In the
current runtime it selects and describes an already-defined source semantic; it
is not a request to convert the source to cash basis, reporting currency, a new
posting state, or a different governing date. The server echoes the effective
report basis metadata, and the browser must not recalculate accounting totals
or group paginated detail rows. Header and line grain must remain distinct to
avoid duplicating document totals.

Developers control filters, group fields, declared measures, default sorts, and table
columns. The current app submits that fixed definition as constrained `viewState` when the
accountant runs the report. Parameters, new measures, source changes, raw expressions,
joins, and SQL are rejected.

Predicates are typed `condition` nodes or nested `group` nodes using `and` or
`or`. Supported operators are `eq`, `ne`, `in`, `not_in`, `contains`, `gt`,
`gte`, `lt`, `lte`, `between`, `is_empty`, and `is_not_empty`, subject to the
field catalog. Maximum depth is 4 with at most 20 conditions.

## Query request and limits

The query request contains the current `definitionDigest`, constrained
`viewState`, and `page`:

```json
{
  "definitionDigest": "host-provided digest",
  "viewState": {
    "columns": ["customer.name", "sales_total"],
    "predicate": {
      "kind": "condition",
      "field": "invoice.date",
      "op": "between",
      "value": ["2026-01-01", "2026-12-31"]
    },
    "groupBy": ["customer.name"],
    "measureIds": ["sales_total"],
    "orderBy": [{ "field": "customer.name", "direction": "asc" }]
  },
  "page": { "size": 100 }
}
```

Interactive limits are 100 rows by default, 500 maximum, 20 columns, 20
conditions, predicate depth 4, and 3 group levels (or the definition's lower
`maxGroupLevels`). The current implementation does not yet enforce every
planned candidate-row, group-cardinality, duration, or response-byte budget.
Do not present planned 100,000-row, 5-second, 5-MiB, or export limits as shipped.

Structured runtime errors currently include `query_invalid`,
`report_definition_stale`, `report_definition_invalid`, `report_not_found`,
`report_source_not_granted`, `report_surface_not_granted`, and
`plugin_unavailable`. The dormant saved-view backend stores company-scoped views and
rejects stale definition digests. It remains future-facing infrastructure and is not
exposed as an end-user report builder.

## Optional SPRKQL authoring

`scripts/sprkql.py` compiles a restricted SQL-like authoring language into an
executable `sourceGrant`, `data`, and table `views` fragment. It never runs SQL;
authors copy the fragment into the root capability and report definition.

```text
SELECT customer.name, SUM(line.amount) AS sales_total
FROM invoice.lines@1
WHERE invoice.date BETWEEN '2026-01-01' AND '2026-12-31'
GROUP BY customer.name
ORDER BY customer.name ASC
```

The compiler supports literal locked filters, AND, grouping, approved
aggregates, and sorting. It rejects parameters, OR, HAVING, joins, subqueries,
comments, DDL/DML, unions, physical table sources, wildcard selection, and
arbitrary functions because those cannot be represented safely in the shipped
definition shape.

See the executable [detail](examples/report-detail/extensions/invoice-detail.json)
and [grouped](examples/report-grouped/extensions/customer-sales.json) examples.
