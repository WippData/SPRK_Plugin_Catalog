from __future__ import annotations

import csv
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "plugin-developer-docs" / "plugin-manifest.schema.json"
EXAMPLES = ROOT / "plugin-developer-docs" / "examples"
ACCOUNTING_SCHEDULES = ROOT / "accounting-schedules"
DOCUMENT_TEMPLATE_DEMO = ROOT / "alternate-invoice-layout-demo"
SPEC = importlib.util.spec_from_file_location(
    "validate_plugin_folder", ROOT / "scripts" / "validate_plugin_folder.py"
)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
sys.modules["validate_plugin_folder"] = validator
SPEC.loader.exec_module(validator)


class PluginFolderValidatorTests(unittest.TestCase):
    def validate(self, folder: Path) -> list[str]:
        errors, warnings = validator.validate(folder, SCHEMA)
        self.assertEqual(warnings, [])
        return errors

    def copied_example(self, name: str, temporary: str) -> Path:
        destination = Path(temporary) / name
        shutil.copytree(EXAMPLES / name, destination)
        return destination

    def update_json(self, path: Path, transform) -> None:
        value = json.loads(path.read_text(encoding="utf-8"))
        transform(value)
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def write_expand_page_example(self, temporary: str) -> Path:
        folder = Path(temporary) / "publisher.expand-fields"
        (folder / "extensions").mkdir(parents=True)
        manifest = {
            "schemaVersion": "2",
            "pluginId": "publisher.expand-fields",
            "name": "Native drawer fields",
            "version": "1.0.0",
            "publisher": {"id": "publisher", "name": "Publisher"},
            "runtime": {"minAppVersion": "1.0.0"},
            "capabilities": {
                "surfaces.contribute": {
                    "required": True,
                    "surfaces": ["customers.drawer.fields"],
                }
            },
            "extensionManifests": [
                {"extensionId": "customer-fields", "path": "extensions/customer-fields.json"}
            ],
        }
        extension = {
            "schemaVersion": "2",
            "extensionId": "customer-fields",
            "type": "expand_page",
            "name": "Customer fields",
            "version": "1.0.0",
            "targets": {"companyScoped": True},
            "resources": [
                {
                    "resourceId": "customer-values",
                    "kind": "records",
                    "schemaVersion": 1,
                    "scope": "company",
                    "access": "host_only",
                    "recordSchema": {
                        "fields": [
                            {"fieldId": "segment", "dataType": "string", "required": False},
                            {"fieldId": "credit-limit", "dataType": "number", "required": False},
                            {"fieldId": "tax-exempt", "dataType": "boolean", "required": False},
                            {"fieldId": "internal-note", "dataType": "string", "required": False},
                        ]
                    },
                }
            ],
            "definition": {
                "definitionVersion": 1,
                "targetPageKey": "customers",
                "addFields": [
                    {
                        "fieldId": "segment",
                        "label": "Segment",
                        "dataType": "string",
                        "required": False,
                        "ui": {
                            "drawer": {
                                "input": "select",
                                "options": {
                                    "kind": "static",
                                    "items": [
                                        {"value": "retail", "label": "Retail"},
                                        {"value": "wholesale", "label": "Wholesale"},
                                    ],
                                },
                            }
                        },
                    },
                    {
                        "fieldId": "credit-limit",
                        "label": "Credit limit",
                        "dataType": "number",
                        "required": False,
                        "ui": {"drawer": {"input": "number"}},
                    },
                    {
                        "fieldId": "tax-exempt",
                        "label": "Tax exempt",
                        "dataType": "boolean",
                        "required": False,
                        "ui": {"drawer": {"input": "checkbox"}},
                    },
                    {
                        "fieldId": "internal-note",
                        "label": "Internal note",
                        "dataType": "string",
                        "required": False,
                        "ui": {"drawer": {"input": "text"}},
                    },
                ],
            },
        }
        (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        (folder / "extensions" / "customer-fields.json").write_text(json.dumps(extension, indent=2) + "\n", encoding="utf-8")
        return folder

    def test_all_documented_examples_are_locally_valid(self) -> None:
        for folder in sorted(path for path in EXAMPLES.iterdir() if path.is_dir()):
            with self.subTest(folder=folder.name):
                self.assertEqual(self.validate(folder), [])

    def test_document_template_demo_is_valid_and_requires_exact_render_grant(self) -> None:
        self.assertEqual(self.validate(DOCUMENT_TEMPLATE_DEMO), [])

        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / DOCUMENT_TEMPLATE_DEMO.name
            shutil.copytree(DOCUMENT_TEMPLATE_DEMO, folder)
            self.update_json(
                folder / "manifest.json",
                lambda manifest: manifest["capabilities"].pop("documents.render"),
            )
            self.assertIn(
                "document template requires capabilities.documents.render.required",
                "\n".join(self.validate(folder)),
            )

        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / DOCUMENT_TEMPLATE_DEMO.name
            shutil.copytree(DOCUMENT_TEMPLATE_DEMO, folder)
            self.update_json(
                folder / "manifest.json",
                lambda manifest: manifest["capabilities"]["documents.render"]["outputs"].append("html"),
            )
            self.assertIn("must be one of", "\n".join(self.validate(folder)))

    def test_rejects_nested_capabilities_invalid_input_and_invented_command(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = self.copied_example("review-import-customers", temporary)

            def break_manifest(manifest: dict) -> None:
                manifest["capabilities"]["api"] = manifest["capabilities"].pop("api.execute")

            def break_actions(extension: dict) -> None:
                action = extension["definition"]["actions"][0]
                action["inputs"] = [
                    {"inputId": "csvText", "label": "CSV", "type": "string"}
                ]
                action["steps"][0] = {
                    "id": "parse-csv",
                    "command": "data.text_to_csv",
                    "with": {"text": "$inputs.csvText"},
                }

            self.update_json(folder / "manifest.json", break_manifest)
            self.update_json(folder / "extensions" / "actions.json", break_actions)
            errors = self.validate(folder)
            joined = "\n".join(errors)
            self.assertIn("manifest.capabilities.api: unknown field", joined)
            self.assertIn("inputId: does not match required pattern", joined)
            self.assertIn("type: must be one of", joined)
            self.assertIn("must match exactly one allowed shape", joined)

    def test_bank_review_requires_account_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = self.copied_example("review-import-bank", temporary)

            def remove_binding(extension: dict) -> None:
                extension["definition"]["actions"][0].pop("binding")

            self.update_json(folder / "extensions" / "actions.json", remove_binding)
            errors = self.validate(folder)
            self.assertIn("bank_register review requires the accounts-to-accounts action binding", "\n".join(errors))

    def test_review_surface_must_match_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = self.copied_example("review-import-customers", temporary)

            def mismatch_surface(extension: dict) -> None:
                extension["definition"]["targetPageKey"] = "vendors"

            self.update_json(folder / "extensions" / "surface.json", mismatch_surface)
            errors = self.validate(folder)
            self.assertIn("customers review must use surface customers", "\n".join(errors))

    def test_master_data_review_must_be_unbound(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = self.copied_example("review-import-customers", temporary)

            def add_binding(extension: dict) -> None:
                extension["definition"]["actions"][0]["binding"] = {
                    "sourceCollection": "customers",
                    "targetType": "customers",
                }

            self.update_json(folder / "extensions" / "actions.json", add_binding)
            errors = self.validate(folder)
            self.assertIn("native master-data header review must omit action.binding", "\n".join(errors))

    def test_unknown_root_and_action_fields_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = self.copied_example("review-import-customers", temporary)

            def add_unknown_root(manifest: dict) -> None:
                manifest["capabilities"]["actions.run"]["scheduled"] = True

            def add_unknown_action(extension: dict) -> None:
                extension["definition"]["actions"][0]["resource"] = "customers"

            self.update_json(folder / "manifest.json", add_unknown_root)
            self.update_json(folder / "extensions" / "actions.json", add_unknown_action)
            errors = self.validate(folder)
            joined = "\n".join(errors)
            self.assertIn("manifest.capabilities.actions.run.scheduled: unknown field", joined)
            self.assertIn("resource: unknown field", joined)

    def test_proposal_requires_typed_mapping_and_exact_target_grant(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = self.copied_example("review-convert-crm", temporary)

            def break_manifest(manifest: dict) -> None:
                manifest["capabilities"]["review"]["proposals"] = [
                    {
                        "target": {
                            "kind": "native",
                            "entity": "vendors",
                            "operation": "create",
                        }
                    }
                ]

            def break_actions(extension: dict) -> None:
                extension["definition"]["fieldMappings"][0]["fields"]["name"] = "lead_name"

            self.update_json(folder / "manifest.json", break_manifest)
            self.update_json(folder / "extensions" / "actions.json", break_actions)
            errors = self.validate(folder)
            joined = "\n".join(errors)
            self.assertIn("must match exactly one allowed shape", joined)

            self.update_json(
                folder / "extensions" / "actions.json",
                lambda extension: extension["definition"]["fieldMappings"][0]["fields"].__setitem__(
                    "name", {"from": "lead_name"}
                ),
            )
            errors = self.validate(folder)
            self.assertIn("proposal target is not granted exactly", "\n".join(errors))

    def test_direct_delta_command_remains_valid_for_compatibility(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = self.copied_example("review-sync-plugin-records", temporary)

            def replace_review(extension: dict) -> None:
                extension["definition"]["actions"][0]["steps"][-1] = {
                    "id": "apply-delta",
                    "command": "resource.apply_delta",
                    "with": {
                        "resource": {
                            "extensionId": "customer-page",
                            "resourceId": "provider-customers",
                        },
                        "identityField": "external_id",
                        "addedSource": "$steps.fetch-customers.safeOutput.customers",
                        "removedMode": "mark",
                        "removedFlagField": "is_inactive",
                    },
                }

            self.update_json(folder / "extensions" / "actions.json", replace_review)
            errors = self.validate(folder)
            self.assertEqual(errors, [])

    def test_plugin_page_run_action_requires_surface_grant(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = self.copied_example("review-convert-crm", temporary)

            def remove_surface_grant(manifest: dict) -> None:
                manifest["capabilities"].pop("surfaces.contribute")

            self.update_json(folder / "manifest.json", remove_surface_grant)
            errors = self.validate(folder)
            self.assertIn(
                "plugin page run_action requires plugin_pages.header.actions",
                "\n".join(errors),
            )

    def test_expand_page_v1_drawer_fields_bundle_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            self.assertEqual(self.validate(self.write_expand_page_example(temporary)), [])

    def test_expand_page_v1_accepts_each_allowlisted_target_and_exact_surface(self) -> None:
        for target in ("accounts", "customers", "vendors", "items"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temporary:
                folder = self.write_expand_page_example(temporary)
                self.update_json(
                    folder / "manifest.json",
                    lambda manifest: manifest["capabilities"]["surfaces.contribute"].__setitem__(
                        "surfaces", [f"{target}.drawer.fields"]
                    ),
                )
                self.update_json(
                    folder / "extensions" / "customer-fields.json",
                    lambda extension: extension["definition"].__setitem__("targetPageKey", target),
                )
                self.assertEqual(self.validate(folder), [])

    def test_expand_page_v1_requires_exact_drawer_surface(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = self.write_expand_page_example(temporary)
            self.update_json(
                folder / "manifest.json",
                lambda manifest: manifest["capabilities"]["surfaces.contribute"].__setitem__(
                    "surfaces", ["customers"]
                ),
            )
            self.assertIn(
                "expand_page requires exact surface grant customers.drawer.fields",
                "\n".join(self.validate(folder)),
            )

    def test_expand_page_v1_resource_schema_must_match_optional_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = self.write_expand_page_example(temporary)

            def break_resource(extension: dict) -> None:
                fields = extension["resources"][0]["recordSchema"]["fields"]
                fields[0]["required"] = True
                fields[1]["dataType"] = "string"

            self.update_json(folder / "extensions" / "customer-fields.json", break_resource)
            joined = "\n".join(self.validate(folder))
            self.assertIn("segment: required must be false", joined)
            self.assertIn("credit-limit: dataType must be 'number'", joined)

    def test_expand_page_v1_rejects_non_drawer_placement_defaults_and_resource_selector(self) -> None:
        mutations = {
            "valueResourceId": lambda extension: extension["definition"].__setitem__(
                "valueResourceId", "customer-values"
            ),
            "defaultValue": lambda extension: extension["definition"]["addFields"][0].__setitem__(
                "defaultValue", "retail"
            ),
            "table": lambda extension: extension["definition"]["addFields"][0]["ui"].__setitem__(
                "table", {"visible": True}
            ),
        }
        for rejected_field, mutation in mutations.items():
            with self.subTest(rejected_field=rejected_field), tempfile.TemporaryDirectory() as temporary:
                folder = self.write_expand_page_example(temporary)
                self.update_json(folder / "extensions" / "customer-fields.json", mutation)
                self.assertIn(
                    f"{rejected_field}: unknown field",
                    "\n".join(self.validate(folder)),
                )

    def test_legacy_expand_page_shape_remains_readable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = self.write_expand_page_example(temporary)

            def make_legacy(extension: dict) -> None:
                extension.pop("targets")
                extension.pop("resources")
                extension["definition"] = {
                    "targetPageId": "plugin-page",
                    "pageActions": {},
                    "rowActions": {},
                }

            self.update_json(folder / "extensions" / "customer-fields.json", make_legacy)
            self.update_json(folder / "manifest.json", lambda manifest: manifest.__setitem__("capabilities", {}))
            self.assertEqual(self.validate(folder), [])

    def test_crm_example_covers_customer_and_draft_invoice_conversion(self) -> None:
        actions = json.loads(
            (EXAMPLES / "review-convert-crm" / "extensions" / "actions.json").read_text()
        )
        mappings = {
            mapping["mappingId"]: mapping
            for mapping in actions["definition"]["fieldMappings"]
        }
        self.assertEqual(
            mappings["customer-from-lead"]["target"],
            {"kind": "native", "entity": "customers", "operation": "create_or_link"},
        )
        invoice = mappings["draft-invoice-from-deal"]
        self.assertEqual(invoice["target"]["operation"], "create_draft")
        self.assertEqual(invoice["fields"]["quantity"], {"value": 1})
        self.assertEqual(invoice["writeback"]["targetIdField"], "invoice_id")

    def test_schema_accepts_draft_bill_and_posted_journal_targets(self) -> None:
        schema = json.loads((ROOT / "plugin-developer-docs" / "plugin-manifest.schema.json").read_text())
        target_schema = schema["$defs"]["ActionProposalTarget"]
        for target in (
            {"kind": "native", "entity": "bills", "operation": "create_draft"},
            {"kind": "native", "entity": "journal_entries", "operation": "post"},
        ):
            self.assertEqual(validator.schema_errors(target, target_schema, schema), [])

    def test_manual_workflow_requires_capability_and_rejects_scheduled_trigger(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = self.copied_example("workflow-renewal-review", temporary)
            self.update_json(
                folder / "manifest.json",
                lambda manifest: manifest["capabilities"].pop("workflows.run"),
            )
            errors = self.validate(folder)
            self.assertIn("requires capabilities.workflows.run.required", "\n".join(errors))

        with tempfile.TemporaryDirectory() as temporary:
            folder = self.copied_example("workflow-renewal-review", temporary)
            self.update_json(
                folder / "extensions" / "renewal-review-workflow.json",
                lambda extension: extension["definition"]["workflows"][0].__setitem__(
                    "trigger", {"type": "scheduled", "cron": "0 0 * * *"}
                ),
            )
            errors = self.validate(folder)
            joined = "\n".join(errors)
            self.assertIn("trigger.type: must equal 'manual'", joined)
            self.assertIn("must match exactly one allowed shape", joined)

    def test_journal_commit_workflow_requires_event_and_record_write_capabilities(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = self.copied_example("workflow-depreciation-posting", temporary)
            self.update_json(
                folder / "manifest.json",
                lambda manifest: manifest["capabilities"].pop("events.subscribe"),
            )
            errors = self.validate(folder)
            self.assertIn(
                "requires capabilities.events.subscribe for accounting.journals.committed",
                "\n".join(errors),
            )

        with tempfile.TemporaryDirectory() as temporary:
            folder = self.copied_example("workflow-depreciation-posting", temporary)
            self.update_json(
                folder / "manifest.json",
                lambda manifest: manifest["capabilities"].pop("records.write"),
            )
            errors = self.validate(folder)
            self.assertIn("records.update requires capabilities.records.write", "\n".join(errors))

    def test_journal_commit_workflow_is_headless_inputless_and_source_filtered(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = self.copied_example("workflow-depreciation-posting", temporary)

            def add_target_and_bad_filter(extension: dict) -> None:
                workflow = extension["definition"]["workflows"][1]
                workflow["targetExtensionId"] = "assets-page"
                workflow["trigger"]["filters"]["sourceWorkflowIds"] = ["missing-workflow"]

            self.update_json(
                folder / "extensions" / "depreciation-workflows.json",
                add_target_and_bad_filter,
            )
            errors = self.validate(folder)
            joined = "\n".join(errors)
            self.assertIn("targetExtensionId: must be omitted for event workflows", joined)
            self.assertIn("sourceWorkflowIds: must reference same-plugin workflows", joined)

        with tempfile.TemporaryDirectory() as temporary:
            folder = self.copied_example("workflow-depreciation-posting", temporary)

            def add_input(extension: dict) -> None:
                extension["definition"]["workflows"][1]["inputs"] = [
                    {"inputId": "unexpected", "label": "Unexpected", "type": "text"}
                ]

            self.update_json(
                folder / "extensions" / "depreciation-workflows.json",
                add_input,
            )
            errors = self.validate(folder)
            self.assertIn("inputs: has too many items", "\n".join(errors))

    def test_records_update_is_event_only_final_and_same_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = self.copied_example("workflow-depreciation-posting", temporary)

            def move_update_to_manual(extension: dict) -> None:
                manual, event = extension["definition"]["workflows"]
                update = event["commands"][0]
                manual["commands"].insert(0, update)

            self.update_json(
                folder / "extensions" / "depreciation-workflows.json",
                move_update_to_manual,
            )
            errors = self.validate(folder)
            joined = "\n".join(errors)
            self.assertIn("records.update is supported only in event workflows", joined)
            self.assertIn("records.update must be final", joined)

        with tempfile.TemporaryDirectory() as temporary:
            folder = self.copied_example("workflow-depreciation-posting", temporary)

            def target_missing_resource(extension: dict) -> None:
                update = extension["definition"]["workflows"][1]["commands"][0]
                update["with"]["resource"] = {
                    "extensionId": "assets-page",
                    "resourceId": "missing-assets",
                }

            self.update_json(
                folder / "extensions" / "depreciation-workflows.json",
                target_missing_resource,
            )
            errors = self.validate(folder)
            self.assertIn(
                "records.update must target a user-accessible same-plugin new_page records resource",
                "\n".join(errors),
            )

    def test_journal_commit_workflow_rejects_manual_only_commands_and_native_queries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = self.copied_example("workflow-depreciation-posting", temporary)

            def add_native_query(extension: dict) -> None:
                event = extension["definition"]["workflows"][1]
                event["commands"].insert(
                    0,
                    {
                        "id": "query-native-accounts",
                        "command": "records.query",
                        "with": {"entity": "accounts", "limit": 10},
                    },
                )

            self.update_json(
                folder / "extensions" / "depreciation-workflows.json",
                add_native_query,
            )
            errors = self.validate(folder)
            self.assertIn(
                "event workflows may query only same-plugin resources",
                "\n".join(errors),
            )

        with tempfile.TemporaryDirectory() as temporary:
            folder = self.copied_example("workflow-depreciation-posting", temporary)

            def add_review_and_loop(extension: dict) -> None:
                event = extension["definition"]["workflows"][1]
                event["commands"][:0] = [
                    {
                        "id": "review-event-records",
                        "command": "review.records",
                        "with": {"source": "$event.journals"},
                    },
                    {
                        "id": "loop-event-records",
                        "command": "control.for_each",
                        "with": {
                            "source": "$event.journals",
                            "onItemError": "fail",
                            "commands": [
                                {
                                    "id": "calculate-event-record",
                                    "command": "calculate",
                                    "with": {
                                        "source": "$item",
                                        "calculations": [
                                            {
                                                "field": "copy",
                                                "valueType": "string",
                                                "expression": {"kind": "field", "field": "sourceRecordId"},
                                            }
                                        ],
                                    },
                                }
                            ],
                        },
                    },
                ]

            self.update_json(
                folder / "extensions" / "depreciation-workflows.json",
                add_review_and_loop,
            )
            errors = self.validate(folder)
            joined = "\n".join(errors)
            self.assertIn("review.records is not allowed in event workflows", joined)
            self.assertIn("control.for_each is not allowed in event workflows", joined)

    def test_event_only_workflow_needs_no_surface_and_write_grant_is_command_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = self.copied_example("workflow-depreciation-posting", temporary)

            def keep_only_unfiltered_event(extension: dict) -> None:
                event = extension["definition"]["workflows"][1]
                event["trigger"].pop("filters")
                extension["definition"]["workflows"] = [event]

            self.update_json(
                folder / "extensions" / "depreciation-workflows.json",
                keep_only_unfiltered_event,
            )

            def remove_manual_capabilities(manifest: dict) -> None:
                manifest["capabilities"].pop("surfaces.contribute")
                manifest["capabilities"].pop("accounting.journal.propose")
                manifest["capabilities"].pop("records.query")

            self.update_json(folder / "manifest.json", remove_manual_capabilities)
            self.assertEqual([], self.validate(folder))

        with tempfile.TemporaryDirectory() as temporary:
            folder = self.copied_example("workflow-depreciation-posting", temporary)

            def keep_event_without_writeback(extension: dict) -> None:
                event = extension["definition"]["workflows"][1]
                event["trigger"].pop("filters")
                event["commands"] = [
                    {
                        "id": "finish-event",
                        "command": "control.stop",
                        "with": {"status": "completed"},
                    }
                ]
                extension["definition"]["workflows"] = [event]

            self.update_json(
                folder / "extensions" / "depreciation-workflows.json",
                keep_event_without_writeback,
            )

            def remove_unused_capabilities(manifest: dict) -> None:
                manifest["capabilities"].pop("surfaces.contribute")
                manifest["capabilities"].pop("accounting.journal.propose")
                manifest["capabilities"].pop("records.query")
                manifest["capabilities"].pop("records.write")

            self.update_json(folder / "manifest.json", remove_unused_capabilities)
            self.assertEqual([], self.validate(folder))

    def test_workflow_rejects_forward_sources_and_nested_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = self.copied_example("workflow-renewal-review", temporary)

            def make_source_forward(extension: dict) -> None:
                commands = extension["definition"]["workflows"][0]["commands"]
                commands[3]["with"]["source"] = "$steps.review-renewals.records"

            self.update_json(
                folder / "extensions" / "renewal-review-workflow.json",
                make_source_forward,
            )
            errors = self.validate(folder)
            self.assertIn("source must reference selection", "\n".join(errors))

        with tempfile.TemporaryDirectory() as temporary:
            folder = self.copied_example("workflow-renewal-review", temporary)

            def put_review_in_branch(extension: dict) -> None:
                branch = extension["definition"]["workflows"][0]["commands"][1]["with"]["then"]
                branch[0] = {
                    "id": "nested-review",
                    "command": "review.records",
                    "with": {"source": "$steps.query-renewals.records"},
                }

            self.update_json(
                folder / "extensions" / "renewal-review-workflow.json",
                put_review_in_branch,
            )
            errors = self.validate(folder)
            self.assertIn("nested branches may contain data-only commands only", "\n".join(errors))

    def test_workflow_rejects_duplicate_global_ids_and_invalid_rich_default(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = self.copied_example("workflow-renewal-review", temporary)

            def duplicate_nested_id(extension: dict) -> None:
                commands = extension["definition"]["workflows"][0]["commands"]
                commands[1]["with"]["then"][0]["id"] = "query-renewals"

            self.update_json(
                folder / "extensions" / "renewal-review-workflow.json",
                duplicate_nested_id,
            )
            errors = self.validate(folder)
            self.assertIn("duplicates another workflow command", "\n".join(errors))

        with tempfile.TemporaryDirectory() as temporary:
            folder = self.copied_example("workflow-renewal-review", temporary)

            def break_money_default(extension: dict) -> None:
                inputs = extension["definition"]["workflows"][0]["inputs"]
                money = next(item for item in inputs if item["inputId"] == "approval-threshold")
                money["defaultValue"] = {"amount": "10000", "currency": "usd"}

            self.update_json(
                folder / "extensions" / "renewal-review-workflow.json",
                break_money_default,
            )
            errors = self.validate(folder)
            self.assertIn("defaultValue: does not match input type", "\n".join(errors))

    def test_workflow_collection_and_graph_bounds_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = self.copied_example("workflow-renewal-review", temporary)

            def add_sort_keys(extension: dict) -> None:
                commands = extension["definition"]["workflows"][0]["commands"]
                sort_command = next(item for item in commands if item["command"] == "records.sort")
                sort_command["with"]["keys"] = [
                    {"field": f"field_{index}", "direction": "asc", "nulls": "last"}
                    for index in range(5)
                ]

            self.update_json(
                folder / "extensions" / "renewal-review-workflow.json",
                add_sort_keys,
            )
            errors = self.validate(folder)
            self.assertIn("must match exactly one allowed shape", "\n".join(errors))

    def test_v2_accounting_schedules_bundle_is_valid(self) -> None:
        self.assertEqual(self.validate(ACCOUNTING_SCHEDULES), [])

    def test_v2_accounting_schedule_requires_host_capabilities(self) -> None:
        for capability in ("accounting.schedules.manage", "accounting.journal.propose"):
            with self.subTest(capability=capability), tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary) / "accounting-schedules"
                shutil.copytree(ACCOUNTING_SCHEDULES, folder)
                self.update_json(
                    folder / "manifest.json",
                    lambda manifest: manifest["capabilities"].pop(capability),
                )
                self.assertIn(
                    f"requires capabilities.{capability}.required",
                    "\n".join(self.validate(folder)),
                )

    def test_v2_accounting_schedule_requires_source_reference_and_typed_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "accounting-schedules"
            shutil.copytree(ACCOUNTING_SCHEDULES, folder)

            def break_definition(extension: dict) -> None:
                fields = extension["definition"]["fields"]
                next(field for field in fields if field["fieldId"] == "sourceReference")["required"] = False
                extension["definition"]["calculation"]["periodCountSource"] = "assetName"

            self.update_json(folder / "extensions" / "fixed-assets.json", break_definition)
            joined = "\n".join(self.validate(folder))
            self.assertIn("requires a required string sourceReference field", joined)
            self.assertIn("periodCountSource: field type must be one of ['number']", joined)

    def test_legacy_accounting_schedule_remains_install_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "accounting-schedules"
            shutil.copytree(ACCOUNTING_SCHEDULES, folder)

            def make_legacy(extension: dict) -> None:
                definition = extension["definition"]
                definition.pop("definitionVersion")
                calculation = definition["calculation"]
                calculation["usefulLifeMonthsSource"] = calculation.pop("periodCountSource")
                calculation.pop("openingRecognizedAmountSource")
                calculation.pop("openingRecognizedThroughSource")
                calculation.pop("postingConvention")

            manifest_path = folder / "manifest.json"
            self.update_json(manifest_path, lambda manifest: manifest.__setitem__("capabilities", {}))
            for extension_name in ("fixed-assets", "prepaid-expenses", "deferred-revenue"):
                self.update_json(folder / "extensions" / f"{extension_name}.json", make_legacy)
            self.assertEqual(self.validate(folder), [])

    def test_accounting_schedule_import_examples_match_declared_headers(self) -> None:
        for extension_path in sorted((ACCOUNTING_SCHEDULES / "extensions").glob("*.json")):
            extension = json.loads(extension_path.read_text(encoding="utf-8"))
            definition = extension["definition"]
            declared = {
                *(field["fieldId"] for field in definition["fields"]),
                *(role["roleId"] for role in definition["accountRoles"]),
            }
            template_path = ACCOUNTING_SCHEDULES / "templates" / f"{extension_path.stem}.csv"
            with template_path.open(newline="", encoding="utf-8") as template_file:
                rows = list(csv.reader(template_file))
            with self.subTest(extension=extension_path.stem):
                self.assertEqual(len(rows), 2)
                self.assertEqual(set(rows[0]), declared)
                self.assertIn("sourceReference", rows[0])
                self.assertEqual(len(rows[0]), len(rows[1]))
                for role in definition["accountRoles"]:
                    account_value = rows[1][rows[0].index(role["roleId"])]
                    self.assertTrue(account_value)
                    self.assertNotEqual(account_value, "account-id")
    def test_manual_workflow_file_input_and_dataset_read_are_valid(self) -> None:
        folder = EXAMPLES / "workflow-file-review"
        self.assertEqual([], self.validate(folder))

        extension = json.loads(
            (folder / "extensions" / "file-review-workflow.json").read_text()
        )
        workflow = extension["definition"]["workflows"][0]
        self.assertEqual(workflow["trigger"], {"type": "manual"})
        self.assertEqual(workflow["inputs"][0]["type"], "file")
        self.assertEqual(
            workflow["commands"][0],
            {
                "id": "load-file",
                "command": "dataset.read",
                "with": {"inputId": "source-file", "limit": 500},
            },
        )

    def test_workflow_file_requires_exact_grant_and_unique_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = self.copied_example("workflow-file-review", temporary)
            self.update_json(
                folder / "manifest.json",
                lambda manifest: manifest["capabilities"]["files.ingest"].__setitem__(
                    "formats", ["csv"]
                ),
            )

            def duplicate_field(extension: dict) -> None:
                fields = extension["definition"]["workflows"][0]["inputs"][0]["file"]["fields"]
                fields[1]["fieldId"] = fields[0]["fieldId"]

            self.update_json(
                folder / "extensions" / "file-review-workflow.json",
                duplicate_field,
            )
            joined = "\n".join(self.validate(folder))
            self.assertIn("formats require matching capabilities.files.ingest grants", joined)
            self.assertIn("file.fields[1].fieldId: duplicate", joined)

    def test_workflow_file_rejects_host_owned_row_identity_field(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = self.copied_example("workflow-file-review", temporary)

            def reserve_id(extension: dict) -> None:
                fields = extension["definition"]["workflows"][0]["inputs"][0]["file"]["fields"]
                fields[0]["fieldId"] = "id"

            self.update_json(
                folder / "extensions" / "file-review-workflow.json",
                reserve_id,
            )
            joined = "\n".join(self.validate(folder))
            self.assertIn("fieldId: reserved by the workflow host", joined)

    def test_dataset_read_requires_a_required_file_within_its_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = self.copied_example("workflow-file-review", temporary)

            def make_optional_and_too_small(extension: dict) -> None:
                workflow = extension["definition"]["workflows"][0]
                workflow["inputs"][0]["required"] = False
                workflow["commands"][0]["with"]["limit"] = 100

            self.update_json(
                folder / "extensions" / "file-review-workflow.json",
                make_optional_and_too_small,
            )
            joined = "\n".join(self.validate(folder))
            self.assertIn("referenced file input must be required", joined)
            self.assertIn("must be at least the referenced file input maxRows", joined)

    def test_dataset_read_requires_a_declared_file_input(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = self.copied_example("workflow-file-review", temporary)

            def point_to_unknown_input(extension: dict) -> None:
                commands = extension["definition"]["workflows"][0]["commands"]
                commands[0]["with"]["inputId"] = "missing-file"

            self.update_json(
                folder / "extensions" / "file-review-workflow.json",
                point_to_unknown_input,
            )
            self.assertIn(
                "with.inputId: must reference a declared file input",
                "\n".join(self.validate(folder)),
            )

    def test_file_input_is_rejected_for_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = self.copied_example("review-import-customers", temporary)

            def add_file_input(extension: dict) -> None:
                extension["definition"]["actions"][0]["inputs"] = [
                    {
                        "inputId": "source-file",
                        "label": "Data file",
                        "type": "file",
                        "file": {
                            "formats": ["csv"],
                            "fields": [
                                {
                                    "fieldId": "name",
                                    "label": "Name",
                                    "dataType": "string",
                                }
                            ],
                        },
                    }
                ]

            self.update_json(folder / "extensions" / "actions.json", add_file_input)
            joined = "\n".join(self.validate(folder))
            self.assertIn("type: must be one of", joined)
            self.assertIn("file: unknown field", joined)
if __name__ == "__main__":
    unittest.main()
