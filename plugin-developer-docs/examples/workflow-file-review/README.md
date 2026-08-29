# Workflow file review example

This non-catalog example demonstrates a user-selected CSV or XLSX file as the
data for a manual workflow. Opening the modal and staging the file do not start
the workflow. The user reviews the selected file and clicks the host's submit
button; only then does the run begin with an opaque staged-dataset reference.

The workflow uses `dataset.read`, a calculation, a filter, and terminal
`review.records`. The plugin never receives raw file bytes or a filesystem path,
and this example does not write plugin, native, or accounting records. After
Submit, normalized and derived rows are retained as workflow audit data even
though the original file bytes are not retained.

`sample-data.csv` is a local demonstration upload. It is not a bundled plugin
dataset and is not referenced by `manifest.json`.

Validate the plugin declaration from the repository root:

```bash
python3 scripts/validate_plugin_folder.py plugin-developer-docs/examples/workflow-file-review
```
