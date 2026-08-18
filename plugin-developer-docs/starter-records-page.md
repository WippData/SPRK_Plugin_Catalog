# Starter Bundle: Host-Rendered Records Page

This is the smallest current schema-v2 plugin: one plugin-owned records resource
and one host-rendered list page. It requires no network, credentials, or custom code.

```text
demo-project-register/
├── manifest.json
└── extensions/
    └── projects-page.json
```

## `manifest.json`

```json
{
  "schemaVersion": "2",
  "pluginId": "demo.project-register",
  "name": "Project Register",
  "version": "1.0.0",
  "publisher": {
    "id": "demo",
    "name": "Demo Publisher",
    "supportEmail": "support@example.com",
    "website": "https://example.com"
  },
  "description": "A host-rendered register of plugin-owned projects.",
  "runtime": {
    "minAppVersion": "1.0.0"
  },
  "capabilities": {},
  "extensionManifests": [
    {
      "extensionId": "projects-page",
      "path": "extensions/projects-page.json"
    }
  ]
}
```

## `extensions/projects-page.json`

```json
{
  "schemaVersion": "2",
  "extensionId": "projects-page",
  "type": "new_page",
  "name": "Projects",
  "version": "1.0.0",
  "description": "Company-scoped project records.",
  "targets": {
    "companyScoped": true
  },
  "resources": [
    {
      "resourceId": "projects",
      "kind": "records",
      "schemaVersion": 1,
      "scope": "company",
      "access": "user",
      "recordSchema": {
        "fields": [
          { "fieldId": "project_code", "dataType": "string", "required": true },
          { "fieldId": "project_name", "dataType": "string", "required": true },
          { "fieldId": "status", "dataType": "string", "required": true },
          { "fieldId": "start_date", "dataType": "date", "required": false },
          { "fieldId": "budget", "dataType": "currency", "required": false }
        ]
      }
    }
  ],
  "definition": {
    "page": {
      "pageId": "projects",
      "pageKind": "list",
      "title": "Projects",
      "route": "projects",
      "dataSource": {
        "kind": "resource",
        "resourceId": "projects"
      }
    },
    "fields": [
      {
        "fieldId": "project_code",
        "label": "Project Code",
        "dataType": "string",
        "required": true,
        "ui": {
          "table": { "visible": true, "width": 160 },
          "drawer": { "input": "text", "visible": true }
        }
      },
      {
        "fieldId": "project_name",
        "label": "Project Name",
        "dataType": "string",
        "required": true,
        "ui": {
          "table": { "visible": true, "width": 260 },
          "drawer": { "input": "text", "visible": true }
        }
      },
      {
        "fieldId": "status",
        "label": "Status",
        "dataType": "string",
        "required": true,
        "defaultValue": "active",
        "ui": {
          "table": { "visible": true, "width": 140 },
          "drawer": {
            "input": "select",
            "visible": true,
            "options": {
              "kind": "static",
              "items": [
                { "value": "active", "label": "Active" },
                { "value": "on_hold", "label": "On Hold" },
                { "value": "complete", "label": "Complete" }
              ]
            }
          }
        }
      },
      {
        "fieldId": "start_date",
        "label": "Start Date",
        "dataType": "date",
        "required": false,
        "ui": {
          "table": { "visible": true, "width": 140 },
          "drawer": { "input": "date", "visible": true }
        }
      },
      {
        "fieldId": "budget",
        "label": "Budget",
        "dataType": "currency",
        "required": false,
        "ui": {
          "table": { "visible": true, "width": 140 },
          "drawer": { "input": "number", "visible": true }
        }
      }
    ],
    "pageActions": [
      { "actionId": "new", "enabled": true },
      { "actionId": "refresh", "enabled": true },
      { "actionId": "export_csv", "enabled": true }
    ],
    "rowActions": [
      { "actionId": "view", "enabled": true },
      { "actionId": "edit", "enabled": true },
      { "actionId": "delete", "enabled": true }
    ]
  }
}
```

## Build the ZIP

Zip the two bundle entries so `manifest.json` is at the archive root:

```bash
cd demo-project-register
zip -r ../demo-project-register-1.0.0.zip manifest.json extensions
```

Then run the complete sequence in [Manifest and Bundle Validation](manifest-and-bundle-validation.md).

## Extend this starter

- Add an import template using the typed `ImportTemplateDefinition` model.
- Add a secure provider integration using the connector/configuration/action
  recipe in [Implementation Recipes](cross-extension-recipes.md).
- Use a transaction page only when line items, calculations, documents, or host
  posting are required.
