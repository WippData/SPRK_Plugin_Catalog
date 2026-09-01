#!/usr/bin/env python3
"""Build and validate the official SPRK plugin catalog using only Python stdlib."""

from __future__ import annotations

import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parent.parent
SOURCE_PATH = ROOT / "catalog.source.json"
CATALOG_PATH = ROOT / "catalog.json"
DIST_DIR = ROOT / "dist"
SCHEMA_REF = "schemas/catalog.schema.json"
REPOSITORY = "WippData/SPRK_Plugin_Catalog"
RAW_CONTENT_BASE_URL = f"https://raw.githubusercontent.com/{REPOSITORY}/main"
OFFICIAL_PUBLISHER = {"id": "sprk", "name": "SPRK"}
SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")
SUPPORTED_SCREENSHOT_SUFFIXES = {".jpeg", ".jpg", ".png", ".webp"}
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


class CatalogError(Exception):
    pass


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogError(f"unable to read JSON {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(value, dict):
        raise CatalogError(f"{path.relative_to(ROOT)} must contain a JSON object")
    return value


def require_string(value: object, field: str, pattern: re.Pattern[str] | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CatalogError(f"{field} must be a non-empty string")
    if pattern and not pattern.fullmatch(value):
        raise CatalogError(f"{field} has an invalid value: {value}")
    return value


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def safe_relative_path(raw: object, field: str) -> PurePosixPath:
    value = PurePosixPath(require_string(raw, field))
    if value.is_absolute() or ".." in value.parts or not value.parts:
        raise CatalogError(f"{field} must be a safe relative path")
    return value


def plugin_files(plugin_dir: Path) -> list[tuple[PurePosixPath, Path]]:
    files: list[tuple[PurePosixPath, Path]] = []
    for path in plugin_dir.rglob("*"):
        if path.is_symlink():
            raise CatalogError(f"symlinks are not allowed in packages: {path.relative_to(ROOT)}")
        if not path.is_file() or path.name == ".DS_Store":
            continue
        relative = PurePosixPath(path.relative_to(plugin_dir).as_posix())
        if relative.parts[0] == "screenshots":
            continue
        files.append((relative, path))
    files.sort(key=lambda item: item[0].as_posix())
    if not files or files[0][0].as_posix() == "":
        raise CatalogError(f"plugin directory is empty: {plugin_dir.relative_to(ROOT)}")
    if not any(relative.as_posix() == "manifest.json" for relative, _ in files):
        raise CatalogError(f"manifest.json must be at archive root: {plugin_dir.relative_to(ROOT)}")
    return files


def build_zip(plugin_dir: Path) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative, path in plugin_files(plugin_dir):
            info = zipfile.ZipInfo(relative.as_posix(), ZIP_TIMESTAMP)
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return output.getvalue()


def validate_plugin(plugin_dir: Path, source_entry: dict) -> tuple[dict, bytes]:
    manifest_path = plugin_dir / "manifest.json"
    manifest = read_json(manifest_path)
    if manifest.get("schemaVersion") != "2":
        raise CatalogError(f"{plugin_dir.name}/manifest.json must use schemaVersion 2")
    if manifest.get("publisher") != OFFICIAL_PUBLISHER:
        raise CatalogError(
            f"{plugin_dir.name}/manifest.json publisher must be exactly {OFFICIAL_PUBLISHER}"
        )

    plugin_id = require_string(manifest.get("pluginId"), f"{plugin_dir.name}.pluginId", IDENTIFIER)
    version = require_string(manifest.get("version"), f"{plugin_id}.version", SEMVER)
    require_string(manifest.get("name"), f"{plugin_id}.name")
    runtime = manifest.get("runtime")
    if not isinstance(runtime, dict):
        raise CatalogError(f"{plugin_id}.runtime must be an object")
    require_string(runtime.get("minAppVersion"), f"{plugin_id}.runtime.minAppVersion", SEMVER)

    refs = manifest.get("extensionManifests")
    if not isinstance(refs, list) or not refs:
        raise CatalogError(f"{plugin_id}.extensionManifests must be a non-empty array")
    seen_extensions: set[str] = set()
    for index, ref in enumerate(refs):
        if not isinstance(ref, dict):
            raise CatalogError(f"{plugin_id}.extensionManifests[{index}] must be an object")
        extension_id = require_string(
            ref.get("extensionId"),
            f"{plugin_id}.extensionManifests[{index}].extensionId",
            IDENTIFIER,
        )
        if extension_id in seen_extensions:
            raise CatalogError(f"{plugin_id} contains duplicate extensionId {extension_id}")
        seen_extensions.add(extension_id)
        relative = safe_relative_path(ref.get("path"), f"{plugin_id}.{extension_id}.path")
        extension_path = plugin_dir.joinpath(*relative.parts)
        if not extension_path.is_file():
            raise CatalogError(f"missing extension manifest: {plugin_dir.name}/{relative}")
        extension = read_json(extension_path)
        if extension.get("schemaVersion") != "2":
            raise CatalogError(f"{plugin_dir.name}/{relative} must use schemaVersion 2")
        if extension.get("extensionId") != extension_id:
            raise CatalogError(f"{plugin_dir.name}/{relative} extensionId does not match manifest reference")
        declared_hash = ref.get("sha256")
        if declared_hash is not None:
            require_string(declared_hash, f"{plugin_id}.{extension_id}.sha256", SHA256)
            actual_hash = sha256_bytes(extension_path.read_bytes())
            if declared_hash != actual_hash:
                raise CatalogError(
                    f"{plugin_id}.{extension_id}.sha256 mismatch: expected {actual_hash}"
                )

    archive_bytes = build_zip(plugin_dir)
    return manifest, archive_bytes


def build_outputs() -> tuple[dict, dict[str, bytes]]:
    source = read_json(SOURCE_PATH)
    if source.get("catalogVersion") != 1:
        raise CatalogError("catalog.source.json catalogVersion must be 1")
    publisher = source.get("publisher")
    if not isinstance(publisher, dict):
        raise CatalogError("catalog.source.json publisher must be an object")
    if {"id": publisher.get("id"), "name": publisher.get("name")} != OFFICIAL_PUBLISHER:
        raise CatalogError(f"catalog publisher must use {OFFICIAL_PUBLISHER}")
    require_string(publisher.get("website"), "publisher.website")
    require_string(publisher.get("supportUrl"), "publisher.supportUrl")

    source_plugins = source.get("plugins")
    if not isinstance(source_plugins, list) or not source_plugins:
        raise CatalogError("catalog.source.json plugins must be a non-empty array")

    catalog_plugins: list[dict] = []
    archives: dict[str, bytes] = {}
    seen_plugins: set[str] = set()
    for index, entry in enumerate(source_plugins):
        if not isinstance(entry, dict):
            raise CatalogError(f"plugins[{index}] must be an object")
        source_dir = safe_relative_path(entry.get("sourceDirectory"), f"plugins[{index}].sourceDirectory")
        plugin_dir = ROOT.joinpath(*source_dir.parts)
        if not plugin_dir.is_dir():
            raise CatalogError(f"plugin source directory does not exist: {source_dir}")
        manifest, archive_bytes = validate_plugin(plugin_dir, entry)
        plugin_id = manifest["pluginId"]
        if source_dir.as_posix() != plugin_id:
            raise CatalogError(
                f"{plugin_id}.sourceDirectory must match its pluginId exactly"
            )
        if plugin_id in seen_plugins:
            raise CatalogError(f"catalog contains duplicate pluginId {plugin_id}")
        seen_plugins.add(plugin_id)
        version = manifest["version"]
        file_name = f"{plugin_id}-{version}.zip"
        tag = f"{plugin_id}-v{version}"
        release = {
            "version": version,
            "schemaVersion": "2",
            "fileName": file_name,
            "assetUrl": f"https://github.com/{REPOSITORY}/releases/download/{tag}/{file_name}",
            "sha256": sha256_bytes(archive_bytes),
            "minAppVersion": manifest["runtime"]["minAppVersion"],
            "releaseNotes": require_string(entry.get("releaseNotes"), f"{plugin_id}.releaseNotes"),
            "publishedAt": require_string(entry.get("publishedAt"), f"{plugin_id}.publishedAt"),
        }
        plugin = {
            "id": plugin_id,
            "name": manifest["name"],
            "summary": require_string(entry.get("summary"), f"{plugin_id}.summary"),
            "free": entry.get("free"),
            "sourceUrl": require_string(entry.get("sourceUrl"), f"{plugin_id}.sourceUrl"),
            "supportUrl": require_string(entry.get("supportUrl"), f"{plugin_id}.supportUrl"),
            "releases": [release],
        }
        if entry.get("free") is not True:
            raise CatalogError(f"{plugin_id}.free must be true in the official free catalog")
        if "license" in entry:
            plugin["license"] = require_string(entry.get("license"), f"{plugin_id}.license")
        if "screenshots" in entry:
            screenshots = entry.get("screenshots")
            if not isinstance(screenshots, list) or not screenshots:
                raise CatalogError(f"{plugin_id}.screenshots must be a non-empty array")
            plugin_screenshots: list[dict[str, str]] = []
            seen_screenshot_paths: set[str] = set()
            for screenshot_index, screenshot in enumerate(screenshots):
                field = f"{plugin_id}.screenshots[{screenshot_index}]"
                if not isinstance(screenshot, dict):
                    raise CatalogError(f"{field} must be an object")
                relative = safe_relative_path(screenshot.get("path"), f"{field}.path")
                if relative.parts[0] != "screenshots":
                    raise CatalogError(f"{field}.path must be under screenshots/")
                if relative.suffix.lower() not in SUPPORTED_SCREENSHOT_SUFFIXES:
                    raise CatalogError(
                        f"{field}.path must use one of "
                        f"{sorted(SUPPORTED_SCREENSHOT_SUFFIXES)}"
                    )
                relative_text = relative.as_posix()
                if relative_text in seen_screenshot_paths:
                    raise CatalogError(f"{plugin_id}.screenshots contains duplicate path {relative_text}")
                seen_screenshot_paths.add(relative_text)
                screenshot_path = plugin_dir.joinpath(*relative.parts)
                if not screenshot_path.is_file():
                    raise CatalogError(f"missing screenshot: {source_dir}/{relative}")
                screenshot_metadata = {
                    "url": f"{RAW_CONTENT_BASE_URL}/{source_dir.as_posix()}/{relative_text}",
                    "alt": require_string(screenshot.get("alt"), f"{field}.alt"),
                }
                if "caption" in screenshot:
                    screenshot_metadata["caption"] = require_string(
                        screenshot.get("caption"), f"{field}.caption"
                    )
                plugin_screenshots.append(screenshot_metadata)
            plugin["screenshots"] = plugin_screenshots
        catalog_plugins.append(plugin)
        archives[file_name] = archive_bytes

    catalog_plugins.sort(key=lambda plugin: plugin["id"])
    catalog = {
        "$schema": SCHEMA_REF,
        "catalogVersion": 1,
        "publisher": publisher,
        "plugins": catalog_plugins,
    }
    validate_catalog(catalog)
    return catalog, archives


def validate_https(value: object, field: str) -> None:
    text = require_string(value, field)
    if not text.startswith("https://"):
        raise CatalogError(f"{field} must use https")


def validate_catalog(catalog: dict) -> None:
    if catalog.get("catalogVersion") != 1 or catalog.get("$schema") != SCHEMA_REF:
        raise CatalogError("generated catalog identity is invalid")
    publisher = catalog.get("publisher")
    if not isinstance(publisher, dict) or publisher.get("id") != "sprk" or publisher.get("name") != "SPRK":
        raise CatalogError("generated catalog publisher is invalid")
    validate_https(publisher.get("website"), "publisher.website")
    validate_https(publisher.get("supportUrl"), "publisher.supportUrl")

    plugins = catalog.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        raise CatalogError("generated catalog plugins must be a non-empty array")
    seen: set[str] = set()
    for plugin in plugins:
        plugin_id = require_string(plugin.get("id"), "plugin.id", IDENTIFIER)
        if plugin_id in seen:
            raise CatalogError(f"generated catalog contains duplicate pluginId {plugin_id}")
        seen.add(plugin_id)
        if plugin.get("free") is not True:
            raise CatalogError(f"{plugin_id}.free must be true")
        require_string(plugin.get("name"), f"{plugin_id}.name")
        require_string(plugin.get("summary"), f"{plugin_id}.summary")
        validate_https(plugin.get("sourceUrl"), f"{plugin_id}.sourceUrl")
        validate_https(plugin.get("supportUrl"), f"{plugin_id}.supportUrl")
        screenshots = plugin.get("screenshots")
        if screenshots is not None:
            if not isinstance(screenshots, list) or not screenshots:
                raise CatalogError(f"{plugin_id}.screenshots must be a non-empty array")
            seen_screenshot_urls: set[str] = set()
            for index, screenshot in enumerate(screenshots):
                field = f"{plugin_id}.screenshots[{index}]"
                if not isinstance(screenshot, dict):
                    raise CatalogError(f"{field} must be an object")
                url = require_string(screenshot.get("url"), f"{field}.url")
                expected_url_prefix = f"{RAW_CONTENT_BASE_URL}/{plugin_id}/screenshots/"
                if not url.startswith(expected_url_prefix):
                    raise CatalogError(
                        f"{field}.url must use the official raw GitHub path for {plugin_id}"
                    )
                if PurePosixPath(url).suffix.lower() not in SUPPORTED_SCREENSHOT_SUFFIXES:
                    raise CatalogError(
                        f"{field}.url must use one of "
                        f"{sorted(SUPPORTED_SCREENSHOT_SUFFIXES)}"
                    )
                if url in seen_screenshot_urls:
                    raise CatalogError(f"{plugin_id}.screenshots contains duplicate URL {url}")
                seen_screenshot_urls.add(url)
                require_string(screenshot.get("alt"), f"{field}.alt")
                if "caption" in screenshot:
                    require_string(screenshot.get("caption"), f"{field}.caption")
        releases = plugin.get("releases")
        if not isinstance(releases, list) or not releases:
            raise CatalogError(f"{plugin_id}.releases must be a non-empty array")
        for release in releases:
            version = require_string(release.get("version"), f"{plugin_id}.release.version", SEMVER)
            if release.get("schemaVersion") != "2":
                raise CatalogError(f"{plugin_id} {version} must use schemaVersion 2")
            expected_file = f"{plugin_id}-{version}.zip"
            if release.get("fileName") != expected_file:
                raise CatalogError(f"{plugin_id} {version} has an invalid fileName")
            expected_tag = f"{plugin_id}-v{version}"
            expected_url = f"https://github.com/{REPOSITORY}/releases/download/{expected_tag}/{expected_file}"
            if release.get("assetUrl") != expected_url:
                raise CatalogError(f"{plugin_id} {version} has an invalid assetUrl")
            require_string(release.get("sha256"), f"{plugin_id}.{version}.sha256", SHA256)
            require_string(release.get("minAppVersion"), f"{plugin_id}.{version}.minAppVersion", SEMVER)
            require_string(release.get("releaseNotes"), f"{plugin_id}.{version}.releaseNotes")
            require_string(release.get("publishedAt"), f"{plugin_id}.{version}.publishedAt")


def catalog_bytes(catalog: dict) -> bytes:
    return (json.dumps(catalog, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def build() -> None:
    catalog, archives = build_outputs()
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    CATALOG_PATH.write_bytes(catalog_bytes(catalog))
    for file_name, contents in archives.items():
        (DIST_DIR / file_name).write_bytes(contents)
    print(f"wrote {CATALOG_PATH.relative_to(ROOT)}")
    for file_name in sorted(archives):
        print(f"wrote dist/{file_name} sha256={sha256_bytes(archives[file_name])}")


def check() -> None:
    catalog, archives = build_outputs()
    expected_catalog = catalog_bytes(catalog)
    if not CATALOG_PATH.is_file() or CATALOG_PATH.read_bytes() != expected_catalog:
        raise CatalogError("catalog.json is missing or stale; run: python3 scripts/catalog.py build")
    actual_assets = {path.name for path in DIST_DIR.glob("*.zip")} if DIST_DIR.is_dir() else set()
    expected_assets = set(archives)
    if actual_assets != expected_assets:
        raise CatalogError(
            f"dist ZIP set is stale: expected {sorted(expected_assets)}, found {sorted(actual_assets)}"
        )
    for file_name, expected in archives.items():
        path = DIST_DIR / file_name
        if path.read_bytes() != expected:
            raise CatalogError(f"dist/{file_name} is stale; run: python3 scripts/catalog.py build")
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if "manifest.json" not in names or any(name.startswith("/") for name in names):
                raise CatalogError(f"dist/{file_name} does not contain a root manifest.json")
    print(
        f"catalog valid: {len(catalog['plugins'])} plugins, "
        f"{len(archives)} deterministic ZIPs"
    )
    for file_name in sorted(archives):
        print(f"dist/{file_name} sha256={sha256_bytes(archives[file_name])}")


def main() -> int:
    command = sys.argv[1] if len(sys.argv) == 2 else ""
    try:
        if command == "build":
            build()
        elif command in {"check", "test"}:
            check()
        else:
            raise CatalogError("usage: python3 scripts/catalog.py <build|check>")
    except CatalogError as exc:
        print(f"catalog error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
