# Bundle Installation and Lifecycle

## Packaging

Create a ZIP with exactly one `manifest.json`. Normally it is at the archive
root. Every extension reference path must resolve to an included file. Archive
paths are non-empty, unique relative paths using `/`; they cannot include
leading/trailing whitespace, null bytes, backslashes, absolute paths, Windows
drive letters, or `..` traversal segments.

| Limit | Maximum |
| --- | ---: |
| Compressed bundle | 10 MiB |
| Expanded bundle | 25 MiB |
| Files | 100 |
| One file | 5 MiB |
| Root or extension manifest | 1 MiB |

If supplied, an extension reference's `sha256` must match the extension file.
The referenced and declared extension IDs must match.

## Install and enablement

Installation is application-wide. Enabling, configuration, connections, and
runtime execution are company-scoped. The install preview checks syntax,
extension relationships, capability coverage, runtime compatibility, and
duplicate plugin IDs.

| Lifecycle state | Meaning |
| --- | --- |
| `enabled` | Installed and enabled for use. |
| `disabled` | Installed but inactive. |
| `requires_reenable` | User re-enablement is required after a state change. |
| `blocked` | A protected-data or lifecycle rule prevents an operation. |
| `invalid` | Stored declarations no longer pass required validation. |

An invalid plugin cannot be enabled. Protected plugin data can prevent removal
until the reported condition is resolved.

## Upgrades

1. Disable the current plugin.
2. Upload a bundle with the same `pluginId`.
3. Use a strictly newer `version`.
4. Preserve compatibility with plugin-owned data and protected-data rules.
5. Review and apply the upgrade preview.

The host rejects changed plugin IDs, enabled current plugins, non-newer
versions, and incompatible protected-data changes.

Treat extension, resource, field, action, operation, auth-method, configuration,
report, schedule, and template IDs as permanent API keys. Add optional fields
before making them required, never change a persisted field type in place, and
test every upgrade with populated prior-version company data. See
[API Versioning](api-versioning.md) for the complete evolution rules.

## Runtime visibility

A valid installed plugin may have no public runtime surface when it declares no
supported active runtime extension or does not have compatible capabilities.
Enable the relevant company-scoped extension and declare the required
capabilities before expecting runtime UI visibility.
