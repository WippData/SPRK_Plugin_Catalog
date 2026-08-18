from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("sprkql", ROOT / "scripts" / "sprkql.py")
assert SPEC and SPEC.loader
sprkql = importlib.util.module_from_spec(SPEC)
sys.modules["sprkql"] = sprkql
SPEC.loader.exec_module(sprkql)


class SprkQLTests(unittest.TestCase):
    def test_compiles_grouped_query_to_canonical_ast(self) -> None:
        result = sprkql.compile_sprkql(
            """SELECT customer.name, SUM(line.amount) AS sales_total,
                      COUNT_DISTINCT(invoice.id) AS invoice_count
               FROM invoice.lines@1
               WHERE invoice.date BETWEEN '2026-01-01' AND '2026-12-31'
                 AND invoice.status = 'posted'
               GROUP BY customer.name
               ORDER BY sales_total DESC, customer.name ASC"""
        )
        self.assertEqual(result["sourceGrant"], {"sourceId": "invoice.lines", "sourceVersion": "1"})
        self.assertEqual(result["views"][0]["columns"], ["customer.name", "sales_total", "invoice_count"])
        self.assertEqual(result["data"]["requiredFilters"][0]["value"], ["2026-01-01", "2026-12-31"])
        self.assertEqual(result["data"]["allowedGroupBy"], ["customer.name"])
        self.assertEqual(result["data"]["defaultSort"][0], {"field": "sales_total", "direction": "desc"})
        self.assertEqual(result["data"]["measures"][0]["function"], "sum")
        self.assertEqual(result["data"]["measures"][1]["function"], "count_distinct")

    def test_rejects_unsafe_or_nonsemantic_syntax(self) -> None:
        rejected = [
            "SELECT invoice.id FROM invoice.lines@1 JOIN gl.lines@1",
            "SELECT invoice.id FROM (SELECT invoice.id FROM invoice.lines@1)",
            "SELECT invoice.id FROM invoice.lines@1 -- comment",
            "DROP TABLE invoices",
            "DELETE FROM sales.invoice_lines@1",
            "SELECT a.id FROM main.invoices@1",
            "SELECT * FROM invoice.lines@1",
            "SELECT invoice.date FROM invoice.lines@1 WHERE invoice.date = :date",
            "SELECT customer.name, SUM(line.amount) AS total FROM invoice.lines@1 GROUP BY customer.name HAVING total > 0",
        ]
        for query in rejected:
            with self.subTest(query=query), self.assertRaises(sprkql.SprkQLError):
                sprkql.compile_sprkql(query)


class ReportSchemaExamplesTests(unittest.TestCase):
    def test_schema_is_json_and_all_local_refs_resolve(self) -> None:
        schema = json.loads((ROOT / "plugin-developer-docs" / "plugin-manifest.schema.json").read_text())
        definitions = schema["$defs"]

        def walk(value):
            if isinstance(value, dict):
                ref = value.get("$ref")
                if isinstance(ref, str) and ref.startswith("#/$defs/"):
                    self.assertIn(ref.removeprefix("#/$defs/"), definitions)
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(schema)
        self.assertIn("reports.query", definitions["PluginCapabilities"]["properties"])
        self.assertIn("reports.catalog.entries", definitions["SurfacesCapability"]["properties"]["surfaces"]["items"]["enum"])
        self.assertEqual(definitions["ReportDefinition"], {"$ref": "#/$defs/LegacyReportDefinition"})

    def test_report_examples_obey_v2_cross_file_contract(self) -> None:
        examples = ROOT / "plugin-developer-docs" / "examples"
        for folder in sorted(path for path in examples.glob("report-*") if path.is_dir()):
            with self.subTest(folder=folder.name):
                manifest = json.loads((folder / "manifest.json").read_text())
                self.assertEqual(manifest["schemaVersion"], "2")
                query_grants = manifest["capabilities"]["reports.query"]["sources"]
                self.assertIn("reports.catalog.entries", manifest["capabilities"]["surfaces.contribute"]["surfaces"])
                for reference in manifest["extensionManifests"]:
                    extension = json.loads((folder / reference["path"]).read_text())
                    self.assertEqual(extension["extensionId"], reference["extensionId"])
                    definition = extension["definition"]
                    self.assertEqual(definition["definitionVersion"], "2")
                    self.assertEqual(extension["type"], "report")
                    self.assertIn({"sourceId": definition["data"]["source"], "sourceVersion": "1"}, query_grants)
                    table = next(view for view in definition["views"] if view["kind"] == "table")
                    self.assertGreater(len(table["columns"]), 0)
                    self.assertLessEqual(len(table["columns"]), 20)
                    self.assertLessEqual(len(table.get("groupBy", [])), 3)


if __name__ == "__main__":
    unittest.main()
