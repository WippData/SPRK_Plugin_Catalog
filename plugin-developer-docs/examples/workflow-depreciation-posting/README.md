# Depreciation posting workflow example

This non-catalog example shows the complete supported journal-commit lifecycle:

1. A user launches `post-depreciation` from the plugin-owned Fixed Assets page.
2. The host shows the selected asset schedules for review and builds balanced
   depreciation journal previews.
3. The host validates and commits the exact reviewed preview through its
   canonical journal service.
4. Only after that commit, `accounting.journals.committed` queues
   `record-depreciation-commit`.
5. `records.update` writes the posting date, native journal ID, and posting hash
   back to the matching same-plugin asset record.

The event workflow is headless: it has no `targetExtensionId` or `inputs`. Its
filters constrain delivery to the manual depreciation workflow in this bundle.
The event payload collection is available as `$event.journals`; each receipt
includes `sourceRecordId`, which is the manual proposal's source-record link.

This example does not post from the event workflow, write native/core records,
run on a schedule, or publish to the catalog. Reversal, void, and supersede
events are not currently supported, so production schedule plugins must not
claim that their writeback automatically follows later journal corrections.

Validate it from the repository root:

```bash
python3 scripts/validate_plugin_folder.py plugin-developer-docs/examples/workflow-depreciation-posting
```
