from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("catalog_builder", ROOT / "scripts" / "catalog.py")
assert SPEC and SPEC.loader
catalog_builder = importlib.util.module_from_spec(SPEC)
sys.modules["catalog_builder"] = catalog_builder
SPEC.loader.exec_module(catalog_builder)


class CatalogFeedTests(unittest.TestCase):
    def test_legacy_feed_excludes_desktop_versioned_plugins(self) -> None:
        app_catalog, _ = catalog_builder.build_outputs()
        legacy_catalog = catalog_builder.legacy_catalog(app_catalog)

        app_ids = {plugin["id"] for plugin in app_catalog["plugins"]}
        legacy_ids = {plugin["id"] for plugin in legacy_catalog["plugins"]}

        self.assertIn("accounting-schedules", app_ids)
        self.assertIn("payroll-journal-assistant", app_ids)
        self.assertNotIn("accounting-schedules", legacy_ids)
        self.assertNotIn("payroll-journal-assistant", legacy_ids)
        self.assertEqual(
            legacy_ids,
            {"month-end-bank-cleanup", "revenue-analysis"},
        )


if __name__ == "__main__":
    unittest.main()
