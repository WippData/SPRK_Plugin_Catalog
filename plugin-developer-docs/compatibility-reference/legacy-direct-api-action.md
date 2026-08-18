# Compatibility Reference: Legacy Direct API Action

This page exists only to identify an older installed-bundle shape. It is not a
starter, is not accepted by the new-plugin JSON Schema, and must not be used by
generators. New plugins use a `connector`, an `actions` extension with an
`api.execute` step, and an `existing_page_actions` contribution with
`kind: "run_action"`.

Older stored bundles may contain an `api_calls` extension referenced by a
`run_api_call` page action. The host retains a tolerant reader for installed
compatibility, but Install Preview rejects these shapes for new authoring.

Do not translate this legacy model into new syntax by renaming fields. Start
from a complete current example in `../examples/` because credentials,
capability grants, safe outputs, action context, and surface references all
require explicit current declarations.
