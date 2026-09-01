from __future__ import annotations

import importlib.util
import io
import sys
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("catalog_builder", ROOT / "scripts" / "catalog.py")
assert SPEC and SPEC.loader
catalog_builder = importlib.util.module_from_spec(SPEC)
sys.modules["catalog_builder"] = catalog_builder
SPEC.loader.exec_module(catalog_builder)


class CatalogFeedTests(unittest.TestCase):
    def test_single_catalog_includes_all_public_plugins(self) -> None:
        catalog, _ = catalog_builder.build_outputs()
        plugin_ids = {plugin["id"] for plugin in catalog["plugins"]}

        self.assertEqual(
            plugin_ids,
            {
                "accounting-schedules",
                "month-end-bank-cleanup",
                "payroll-journal-assistant",
                "revenue-analysis",
            },
        )

    def test_app_feed_includes_lazy_github_screenshot_metadata(self) -> None:
        app_catalog, _ = catalog_builder.build_outputs()
        plugins = {plugin["id"]: plugin for plugin in app_catalog["plugins"]}
        source = catalog_builder.read_json(catalog_builder.SOURCE_PATH)
        self.assertEqual(
            [entry["sourceDirectory"] for entry in source["plugins"]],
            [plugin["id"] for plugin in app_catalog["plugins"]],
        )

        expected_files = {
            "accounting-schedules": [
                "fixed-assets-overview.jpg",
                "fixed-assets-schedule-lines.jpg",
                "fixed-assets-calculated-schedule.jpg",
                "fixed-assets-posting-review.jpg",
                "fixed-assets-journal-posted.jpg",
            ],
            "payroll-journal-assistant": [
                "gusto-account-mappings.jpg",
                "gusto-payroll-review.jpg",
                "gusto-journal-preview.jpg",
                "gusto-journal-posted.jpg",
            ],
        }
        for plugin_id, file_names in expected_files.items():
            screenshots = plugins[plugin_id]["screenshots"]
            self.assertEqual(len(screenshots), len(file_names))
            self.assertEqual(
                [screenshot["url"] for screenshot in screenshots],
                [
                    f"{catalog_builder.RAW_CONTENT_BASE_URL}/{plugin_id}/screenshots/{file_name}"
                    for file_name in file_names
                ],
            )
            self.assertTrue(all(screenshot["alt"].strip() for screenshot in screenshots))
            self.assertTrue(all(screenshot["caption"].strip() for screenshot in screenshots))

    def test_screenshots_are_not_stored_in_plugin_archives(self) -> None:
        _, archives = catalog_builder.build_outputs()

        for file_name, contents in archives.items():
            with zipfile.ZipFile(io.BytesIO(contents)) as archive:
                self.assertFalse(
                    any(name.startswith("screenshots/") for name in archive.namelist()),
                    f"{file_name} unexpectedly includes screenshot bytes",
                )

    def test_screenshot_url_cannot_cross_plugin_directories(self) -> None:
        app_catalog, _ = catalog_builder.build_outputs()
        plugin = next(
            plugin
            for plugin in app_catalog["plugins"]
            if plugin["id"] == "accounting-schedules"
        )
        plugin["screenshots"][0]["url"] = (
            f"{catalog_builder.RAW_CONTENT_BASE_URL}/payroll-journal-assistant/"
            "screenshots/gusto-account-mappings.png"
        )

        with self.assertRaisesRegex(
            catalog_builder.CatalogError,
            "official raw GitHub path for accounting-schedules",
        ):
            catalog_builder.validate_catalog(app_catalog)


if __name__ == "__main__":
    unittest.main()
