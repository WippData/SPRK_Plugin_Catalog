# SPRK Plugin Catalog

Official free-plugin catalog for SPRK, published from
[`WippData/SPRK_Plugin_Catalog`](https://github.com/WippData/SPRK_Plugin_Catalog).
All supported apps use one canonical catalog URL:

```text
https://raw.githubusercontent.com/WippData/SPRK_Plugin_Catalog/main/catalog.json
```

This repository intentionally has one publisher identity:

```json
{
  "id": "sprk",
  "name": "SPRK"
}
```

Only manifest schema `2` packages are cataloged. The existing `employees/` source and
`employees.zip` are preserved as legacy schema `1.0` examples and are intentionally absent
from `catalog.source.json`, `catalog.json`, and `dist/`. Their presence is not a claim that
the catalog or current installer supports schema `1.0`.

## Repository layout

- `catalog.source.json`: publisher-maintained release metadata and package source directories.
- `catalog.json`: generated public catalog consumed by SPRK apps. Each release's
  `minAppVersion` keeps unsupported plugins out of older app versions.
- `schemas/catalog.schema.json`: public JSON Schema for `catalog.json`.
- `scripts/catalog.py`: dependency-free validation and deterministic ZIP builder.
- `scripts/sprkql.py`: restricted SQL-like authoring helper for native table reports.
- `plugin-developer-docs/`: normative schema-v2 plugin developer guide, JSON Schema,
  report guide, and executable examples.
- `tests/`: developer-tooling and documentation contract tests.
- `dist/`: generated release assets; each archive has `manifest.json` at its root.
- `month-end-bank-cleanup/` and `revenue-analysis/`: cataloged schema `2` sources.
- `payroll-journal-assistant/`: app-0.4.29 Payroll Journal Assistant source with
  reviewed generic and Gusto-shaped journal imports.
- `employees/`: preserved, uncataloged legacy schema `1.0` source.

Optional plugin-level `screenshots` metadata in the generated catalog contains a raw GitHub
content `url`, accessible `alt` text, and an optional display `caption`. Screenshot files
remain repository-hosted under each source plugin's `screenshots/` directory and are
deliberately excluded from the installable ZIP, so clients can fetch image bytes only when
a user opens a screenshot view.

Pre-existing ZIPs at the repository root are preserved staging artifacts, not release
assets. Only the deterministic ZIPs generated under `dist/` are referenced by the catalog
or should be uploaded to GitHub releases.

## Build and validate

Python 3 is the only required tool.

```bash
python3 scripts/catalog.py build
python3 scripts/catalog.py check
```

The equivalent npm-friendly commands are:

```bash
npm run build
npm test
```

`npm test` runs both the plugin developer documentation/tooling contract tests
and the deterministic catalog check.

Plugin developers should start with
[`plugin-developer-docs/README.md`](plugin-developer-docs/README.md). Complete
validated examples cover detail reports, grouped reports, bank and customer
review imports, CRM-to-native conversions, reviewed provider snapshots, a
non-catalog manual workflow with branching, collections, rich inputs, and
execution context, and a manual file-data workflow. A separate non-catalog depreciation example covers reviewed
journal proposal, exact-hash commit, journal-commit event delivery, and
same-plugin schedule writeback.
Validate any plugin folder with:

```bash
npm run validate:plugin -- path/to/plugin-folder
```

For native custom reports, also use the
[`Native Custom Reports`](plugin-developer-docs/native-custom-reports.md) guide
and exercise the restricted SPRKQL compiler with:

```bash
python3 -m unittest discover -s tests -p 'test*.py'
```

`build` validates each package and screenshot reference, verifies every declared extension
SHA-256, creates sorted ZIPs with fixed timestamps and file modes, computes each asset
SHA-256, and regenerates the catalog. Screenshot directories are not packaged.
`check` recreates those outputs in memory and fails if either committed catalog or any ZIP
bytes are stale.

## Publisher workflow

1. Change a schema `2` plugin in its source directory. Keep `publisher` exactly
   `{"id":"sprk","name":"SPRK"}`.
2. If `extensionManifests[]` declares `sha256`, recompute it from the exact extension JSON
   bytes and update the manifest.
3. Update the plugin version and its entry in `catalog.source.json`, including release notes
   and `publishedAt`.
4. Run `python3 scripts/catalog.py build` and `python3 scripts/catalog.py check`.
5. Review the manifest, generated catalog feed, asset filename, and reported SHA-256.
6. Commit the source, catalog, and deterministic ZIP together, then merge to `main`.
7. Create one GitHub release whose tag is `<plugin-id>-v<version>` and upload only the
   matching `dist/<plugin-id>-<version>.zip`.
8. Confirm the published asset URL and SHA-256 match the applicable catalog feed before announcing it.

Example release commands after the reviewed commit is on `main`:

```bash
git tag -a demo-credentialed-github-api-v1.1.0 -m "Credentialed GitHub API Demo 1.1.0"
git push origin demo-credentialed-github-api-v1.1.0
gh release create demo-credentialed-github-api-v1.1.0 \
  dist/demo-credentialed-github-api-1.1.0.zip \
  --repo WippData/SPRK_Plugin_Catalog \
  --title "Credentialed GitHub API Demo 1.1.0" \
  --notes "Initial official catalog release."

```

The catalog is deliberately simple: public manual GitHub releases, free plugins, one
official publisher, no private repositories, signing infrastructure, key rotation, or
automatic release publishing.
