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
PAYROLL_JOURNAL_ASSISTANT = ROOT / "payroll-journal-assistant"
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

    def test_all_documented_examples_are_locally_valid(self) -> None:
        for folder in sorted(path for path in EXAMPLES.iterdir() if path.is_dir()):
            with self.subTest(folder=folder.name):
                self.assertEqual(self.validate(folder), [])

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
            self.assertIn("trigger.cron: unknown field", joined)

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

    def test_payroll_journal_assistant_bundle_is_valid_and_patch_gated(self) -> None:
        self.assertEqual(self.validate(PAYROLL_JOURNAL_ASSISTANT), [])
        manifest = json.loads(
            (PAYROLL_JOURNAL_ASSISTANT / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["runtime"]["minAppVersion"], "0.4.29")
        self.assertEqual(
            {item["extensionId"] for item in manifest["extensionManifests"]},
            {"payroll-account-mappings", "payroll-journal-workflows"},
        )

    def test_payroll_templates_match_declared_file_headers(self) -> None:
        extension = json.loads(
            (
                PAYROLL_JOURNAL_ASSISTANT
                / "extensions"
                / "payroll-journal-workflows.json"
            ).read_text(encoding="utf-8")
        )
        workflow = extension["definition"]["workflows"][0]
        file_input = next(item for item in workflow["inputs"] if item["type"] == "file")
        fields = file_input["file"]["fields"]

        def normalized(value: str) -> str:
            return "".join(character for character in value.strip().lower() if character.isalnum())

        owners: dict[str, set[str]] = {}
        for field in fields:
            for candidate in (field["fieldId"], field["label"], *field.get("aliases", [])):
                owners.setdefault(normalized(candidate), set()).add(field["fieldId"])

        for template_name in (
            "generic-payroll-journal-lines.csv",
            "gusto-general-ledger-lines.csv",
        ):
            with (
                PAYROLL_JOURNAL_ASSISTANT / "templates" / template_name
            ).open(newline="", encoding="utf-8") as template_file:
                headers = next(csv.reader(template_file))
            with self.subTest(template=template_name):
                for header in headers:
                    self.assertEqual(owners.get(normalized(header)), {next(iter(owners[normalized(header)]))})

        aliases = {
            field["fieldId"]: field.get("aliases", [])
            for field in fields
        }
        self.assertEqual(aliases["source_type"], ["Account Type"])
        self.assertEqual(aliases["source_description"], ["Account Description"])

        with (
            PAYROLL_JOURNAL_ASSISTANT
            / "templates"
            / "gusto-general-ledger-lines.csv"
        ).open(newline="", encoding="utf-8") as template_file:
            rows = list(csv.DictReader(template_file))
        self.assertEqual(
            {row["Account Type"] for row in rows},
            {"RegularWages", "EmployerTax", "DebitNetPay", "DebitTax"},
        )
        self.assertEqual(
            sum(float(row["Debit"] or 0) for row in rows),
            sum(float(row["Credit"] or 0) for row in rows),
        )

    def test_payroll_file_aliases_fail_closed_on_ambiguous_headers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "payroll-journal-assistant"
            shutil.copytree(PAYROLL_JOURNAL_ASSISTANT, folder)

            def collide_alias(extension: dict) -> None:
                fields = extension["definition"]["workflows"][0]["inputs"][0]["file"]["fields"]
                next(field for field in fields if field["fieldId"] == "department")["aliases"] = ["Job"]

            self.update_json(
                folder / "extensions" / "payroll-journal-workflows.json",
                collide_alias,
            )
            self.assertIn("header name conflicts with field job", "\n".join(self.validate(folder)))

    def test_grouped_journal_line_accepts_one_or_both_sides_but_not_neither(self) -> None:
        for removed, valid in ((["credit"], True), ([], True), (["debit", "credit"], False)):
            with self.subTest(removed=removed), tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary) / "payroll-journal-assistant"
                shutil.copytree(PAYROLL_JOURNAL_ASSISTANT, folder)

                def remove_sides(extension: dict) -> None:
                    preview = extension["definition"]["workflows"][0]["commands"][-1]
                    line = preview["with"]["entry"]["line"]
                    for side in removed:
                        line.pop(side)

                self.update_json(
                    folder / "extensions" / "payroll-journal-workflows.json",
                    remove_sides,
                )
                errors = self.validate(folder)
                if valid:
                    self.assertEqual(errors, [])
                else:
                    self.assertIn("must match exactly one allowed shape", "\n".join(errors))

    def test_payroll_deduplication_uses_one_stable_run_identity(self) -> None:
        extension = json.loads(
            (
                PAYROLL_JOURNAL_ASSISTANT
                / "extensions"
                / "payroll-journal-workflows.json"
            ).read_text(encoding="utf-8")
        )
        workflow = extension["definition"]["workflows"][0]
        preview = workflow["commands"][-1]["with"]
        self.assertEqual(preview["shape"], "line_records")
        self.assertEqual(preview["deduplication"], {
            "mode": "source_record",
            "onChange": "correction_required",
        })
        self.assertEqual(preview["entry"]["entryKey"], preview["entry"]["sourceRecordId"])
        self.assertEqual(preview["entry"]["sourceRecordId"], {
            "kind": "field",
            "field": "payroll_source_id",
        })

    def test_fixed_entry_shape_accepts_explicit_source_deduplication(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        expression = {"kind": "value", "value": "fixed"}
        preview = {
            "source": "$steps.review.records",
            "deduplication": {
                "mode": "source_record",
                "onChange": "correction_required",
            },
            "entry": {
                "date": {"kind": "value", "value": "2026-08-29"},
                "sourceRecordId": expression,
                "lines": [
                    {"accountId": expression, "debit": {"kind": "value", "value": 1}},
                    {"accountId": expression, "credit": {"kind": "value", "value": 1}},
                ],
            },
        }
        self.assertEqual(
            validator.schema_errors(
                preview,
                schema["$defs"]["WorkflowJournalPreviewWith"],
                schema,
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
