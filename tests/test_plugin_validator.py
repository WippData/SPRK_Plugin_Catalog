from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
