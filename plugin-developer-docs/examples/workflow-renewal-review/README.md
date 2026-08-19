# Renewal review workflow example

This non-catalog example shows a schema-v2, definition-version-1 manual workflow attached to a plugin-owned list page. It demonstrates optional selected rows, rich host-rendered inputs, context expressions, deterministic collection operations, bounded branching, lineage, and terminal host review.

It deliberately does not publish a schedule, background job, connector, direct native write, or catalog package.

Validate it from the repository root:

```bash
python3 scripts/validate_plugin_folder.py plugin-developer-docs/examples/workflow-renewal-review
```
