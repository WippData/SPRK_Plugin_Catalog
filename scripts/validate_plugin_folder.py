#!/usr/bin/env python3
"""Validate a schema-v2 SPRK plugin folder without third-party dependencies.

This is the local authoring gate. It applies the normative JSON Schema to the
root and every referenced extension, then checks relationships which JSON
Schema cannot express: capability coverage, connector/action/surface
references, safe-output review mappings, and currently executable review
topologies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCHEMA = ROOT / "plugin-developer-docs" / "plugin-manifest.schema.json"
IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")

REVIEW_FIELDS: dict[str, dict[str, tuple[str, bool]]] = {
    "bank_register": {
        "sourceTransactionId": ("string", True), "date": ("date", True),
        "amount": ("number", True), "description": ("string", False),
        "memo": ("string", False), "checkNo": ("string", False),
        "currency": ("string", False), "vendorId": ("string", False),
        "vendorName": ("string", False), "customerId": ("string", False),
        "customerName": ("string", False),
    },
    "accounts": {
        "code": ("string", False), "name": ("string", True),
        "type": ("string", True), "subtype": ("string", False),
        "description": ("string", False), "nonPosting": ("boolean", False),
        "controlAccount": ("boolean", False), "reconcileAccount": ("boolean", False),
        "isActive": ("boolean", False), "parentId": ("string", False),
        "parentAccountName": ("string", False),
    },
    "customers": {
        "name": ("string", True), "company": ("string", False),
        "email": ("string", False), "phone": ("string", False),
        "isActive": ("boolean", False), "defaultIncomeAccountId": ("string", False),
        "address1": ("string", False), "address2": ("string", False),
        "city": ("string", False), "state": ("string", False),
        "postalCode": ("string", False), "country": ("string", False),
    },
    "vendors": {
        "name": ("string", True), "company": ("string", False),
        "email": ("string", False), "phone": ("string", False),
        "is1099": ("boolean", False), "isActive": ("boolean", False),
        "defaultExpenseAccountId": ("string", False), "address1": ("string", False),
        "address2": ("string", False), "city": ("string", False),
        "state": ("string", False), "postalCode": ("string", False),
        "country": ("string", False),
    },
    "items": {
        "description": ("string", True), "itemType": ("string", False),
        "sku": ("string", False), "unitPrice": ("number", False),
        "buyPrice": ("number", False), "incomeAccountId": ("string", False),
        "expenseAccountId": ("string", False), "unitOfMeasure": ("string", False),
        "isActive": ("boolean", False),
    },
}
REVIEW_SURFACES = {
    "bank_register": "banking.import.source.actions",
    "accounts": "chart",
    "customers": "customers",
    "vendors": "vendors",
    "items": "items",
}


class ValidationFailure(Exception):
    pass


def load_json(path: Path, label: str, errors: list[str]) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        errors.append(f"{label}: could not be read ({exc})")
        return None
    except json.JSONDecodeError as exc:
        errors.append(f"{label}: invalid JSON ({exc.msg} at line {exc.lineno})")
        return None
    if not isinstance(value, dict):
        errors.append(f"{label}: must contain a JSON object")
        return None
    return value


def resolve_ref(root: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ValidationFailure(f"unsupported schema reference {ref}")
    value: Any = root
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        value = value[part]
    if not isinstance(value, dict):
        raise ValidationFailure(f"schema reference {ref} does not resolve to an object")
    return value


def json_type_matches(value: Any, expected: str) -> bool:
    return {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "boolean": isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "null": value is None,
    }.get(expected, True)


def schema_errors(value: Any, schema: dict[str, Any], root: dict[str, Any], path: str = "$") -> list[str]:
    if "$ref" in schema:
        return schema_errors(value, resolve_ref(root, schema["$ref"]), root, path)

    errors: list[str] = []
    if "allOf" in schema:
        for child in schema["allOf"]:
            errors.extend(schema_errors(value, child, root, path))
    if "anyOf" in schema:
        branches = [schema_errors(value, child, root, path) for child in schema["anyOf"]]
        if not any(not branch for branch in branches):
            errors.append(f"{path}: must match at least one allowed shape")
    if "oneOf" in schema:
        branches = [schema_errors(value, child, root, path) for child in schema["oneOf"]]
        matches = sum(1 for branch in branches if not branch)
        if matches != 1:
            detail = next((branch[0] for branch in branches if branch), "ambiguous match")
            errors.append(f"{path}: must match exactly one allowed shape ({detail})")

    condition = schema.get("if")
    if isinstance(condition, dict) and not schema_errors(value, condition, root, path):
        if isinstance(schema.get("then"), dict):
            errors.extend(schema_errors(value, schema["then"], root, path))
    elif isinstance(condition, dict) and isinstance(schema.get("else"), dict):
        errors.extend(schema_errors(value, schema["else"], root, path))

    expected = schema.get("type")
    if isinstance(expected, str) and not json_type_matches(value, expected):
        return errors + [f"{path}: expected {expected}, got {type(value).__name__}"]
    if isinstance(expected, list) and not any(json_type_matches(value, item) for item in expected):
        return errors + [f"{path}: has an invalid JSON type"]
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: must equal {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: must be one of {schema['enum']!r}")

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}.{key}: is required")
        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            for key, child in properties.items():
                if key in value and isinstance(child, dict):
                    errors.extend(schema_errors(value[key], child, root, f"{path}.{key}"))
        additional = schema.get("additionalProperties", True)
        for key in value:
            if key in properties:
                continue
            if additional is False:
                errors.append(f"{path}.{key}: unknown field")
            elif isinstance(additional, dict):
                errors.extend(schema_errors(value[key], additional, root, f"{path}.{key}"))
        if isinstance(schema.get("propertyNames"), dict):
            for key in value:
                errors.extend(schema_errors(key, schema["propertyNames"], root, f"{path}.{key}"))
        if len(value) < schema.get("minProperties", 0):
            errors.append(f"{path}: has too few properties")
        if "maxProperties" in schema and len(value) > schema["maxProperties"]:
            errors.append(f"{path}: has too many properties")

    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: has too few items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}: has too many items")
        if schema.get("uniqueItems"):
            encoded = [json.dumps(item, sort_keys=True, separators=(",", ":")) for item in value]
            if len(set(encoded)) != len(encoded):
                errors.append(f"{path}: contains duplicate items")
        if isinstance(schema.get("items"), dict):
            for index, item in enumerate(value):
                errors.extend(schema_errors(item, schema["items"], root, f"{path}[{index}]"))
        if isinstance(schema.get("contains"), dict) and not any(
            not schema_errors(item, schema["contains"], root, f"{path}[{index}]")
            for index, item in enumerate(value)
        ):
            errors.append(f"{path}: does not contain a required item")

    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path}: is too short")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path}: is too long")
        # JSON Schema's pattern keyword searches for a match; it does not imply
        # that the regular expression must consume the entire string.
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            errors.append(f"{path}: does not match required pattern")
        if schema.get("format") == "uri":
            parsed = urlparse(value)
            if not parsed.scheme or not parsed.netloc:
                errors.append(f"{path}: must be an absolute URI")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and not math.isfinite(value):
            errors.append(f"{path}: must be finite")
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: must be at least {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: must be at most {schema['maximum']}")
    return errors


def capability_required(manifest: dict[str, Any], key: str) -> bool:
    capability = manifest.get("capabilities", {}).get(key, {})
    return isinstance(capability, dict) and capability.get("required") is True


def capability_list(manifest: dict[str, Any], key: str, field: str) -> list[Any]:
    capability = manifest.get("capabilities", {}).get(key, {})
    value = capability.get(field, []) if isinstance(capability, dict) else []
    return value if isinstance(value, list) else []


def source_parts(source: str) -> tuple[str, str] | None:
    match = re.fullmatch(r"\$steps\.([a-z0-9][a-z0-9._-]{0,127})\.safeOutput\.([a-z0-9][a-z0-9._-]{0,127})", source)
    return (match.group(1), match.group(2)) if match else None


def bundle_errors(manifest: dict[str, Any], extensions: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    actions: dict[tuple[str, str], dict[str, Any]] = {}
    connector_operations: dict[tuple[str, str], dict[str, Any]] = {}
    configuration_count = 0

    for extension_id, extension in extensions.items():
        ext_type = extension.get("type")
        definition = extension.get("definition", {})
        if ext_type == "connector":
            if not capability_required(manifest, "internetAccess"):
                errors.append(f"extensions.{extension_id}: connector requires capabilities.internetAccess.required")
            if not capability_required(manifest, "api.execute"):
                errors.append(f"extensions.{extension_id}: connector requires capabilities.api.execute.required")
            resources = {item.get("resourceId"): item for item in extension.get("resources", [])}
            for operation in definition.get("api", {}).get("operations", []):
                connector_operations[(extension_id, operation.get("operationId"))] = operation
                if operation.get("method") not in capability_list(manifest, "api.execute", "methods"):
                    errors.append(f"extensions.{extension_id}.definition.api.operations.{operation.get('operationId')}: HTTP method is not granted")
            if sum(1 for resource in resources.values() if resource.get("kind") == "connector") != 1:
                errors.append(f"extensions.{extension_id}: connector must declare exactly one connector resource")
        elif ext_type == "plugin_configuration":
            configuration_count += 1
        elif ext_type == "actions":
            if not capability_required(manifest, "actions.run") or "manual" not in capability_list(manifest, "actions.run", "allowedTriggers"):
                errors.append(f"extensions.{extension_id}: actions require capabilities.actions.run manual")
            for action in definition.get("actions", []):
                actions[(extension_id, action.get("actionId"))] = action

    if configuration_count > 1:
        errors.append("bundle: at most one plugin_configuration extension is allowed")

    for extension_id, extension in extensions.items():
        definition = extension.get("definition", {})
        if extension.get("type") == "plugin_configuration":
            for section in definition.get("sections", []):
                connection = section.get("connection")
                if isinstance(connection, dict):
                    ref = connection.get("connector", {})
                    connector = extensions.get(ref.get("extensionId"))
                    if not connector or connector.get("type") != "connector":
                        errors.append(f"extensions.{extension_id}.definition.sections.{section.get('sectionId')}: connector extension does not exist")
                    elif not any(resource.get("resourceId") == ref.get("resourceId") and resource.get("kind") == "connector" for resource in connector.get("resources", [])):
                        errors.append(f"extensions.{extension_id}.definition.sections.{section.get('sectionId')}: connector resource does not exist")
                    for action in connection.get("actions", []):
                        operation_id = action.get("operationId")
                        if action.get("kind") == "discover_connection" and (ref.get("extensionId"), operation_id) not in connector_operations:
                            errors.append(f"extensions.{extension_id}.definition.sections.{section.get('sectionId')}: discovery operation does not exist")
                bindings = section.get("bindings")
                if isinstance(bindings, dict):
                    if not capability_required(manifest, "plugin.bindings.manage") or bindings.get("targetType") not in capability_list(manifest, "plugin.bindings.manage", "targets"):
                        errors.append(f"extensions.{extension_id}.definition.sections.{section.get('sectionId')}: binding target is not granted")

    review_targets_by_action: dict[tuple[str, str], str] = {}
    for (extension_id, action_id), action in actions.items():
        binding = action.get("binding")
        if isinstance(binding, dict):
            if not capability_required(manifest, "plugin.bindings.manage") or binding.get("targetType") not in capability_list(manifest, "plugin.bindings.manage", "targets"):
                errors.append(f"extensions.{extension_id}.actions.{action_id}: binding target is not granted")
        safe_outputs: dict[tuple[str, str], dict[str, Any]] = {}
        for index, step in enumerate(action.get("steps", [])):
            command = step.get("command")
            step_id = step.get("id")
            spec = step.get("with", {})
            if command and command.startswith("data."):
                grants = capability_list(manifest, "data", "sprk")
                allowed = any(grant.get("entity") == spec.get("entity") and command[5:] in grant.get("operations", []) for grant in grants if isinstance(grant, dict))
                if not capability_required(manifest, "data") or not allowed:
                    errors.append(f"extensions.{extension_id}.actions.{action_id}.steps.{step_id}: data operation is not granted")
            elif command == "api.execute":
                ref = spec.get("connector", {})
                connector = extensions.get(ref.get("extensionId"))
                operation = connector_operations.get((ref.get("extensionId"), ref.get("operationId")))
                if not connector or connector.get("type") != "connector" or not operation:
                    errors.append(f"extensions.{extension_id}.actions.{action_id}.steps.{step_id}: connector operation does not exist")
                elif operation.get("connectionDiscovery") is not None:
                    errors.append(f"extensions.{extension_id}.actions.{action_id}.steps.{step_id}: discovery operations cannot be executed by an action")
                if not any(resource.get("resourceId") == ref.get("resourceId") and resource.get("kind") == "connector" for resource in (connector or {}).get("resources", [])):
                    errors.append(f"extensions.{extension_id}.actions.{action_id}.steps.{step_id}: connector resource does not exist")
                for output in spec.get("safeOutputs", []):
                    safe_outputs[(step_id, output.get("collection"))] = output
            elif command == "review.import":
                target = spec.get("targetEntity")
                review_targets_by_action[(extension_id, action_id)] = target
                grants = [grant.get("targetEntity") for grant in capability_list(manifest, "review", "imports") if isinstance(grant, dict)]
                if not capability_required(manifest, "review") or target not in grants:
                    errors.append(f"extensions.{extension_id}.actions.{action_id}.steps.{step_id}: review target is not granted")
                parts = source_parts(spec.get("source", ""))
                output = safe_outputs.get(parts) if parts else None
                if output is None:
                    errors.append(f"extensions.{extension_id}.actions.{action_id}.steps.{step_id}: review source must reference an earlier safe output")
                    continue
                output_fields = output.get("fields", {})
                for target_field, source_field in spec.get("fields", {}).items():
                    expected = REVIEW_FIELDS.get(target, {}).get(target_field)
                    actual = output_fields.get(source_field)
                    if expected is None or actual is None:
                        errors.append(f"extensions.{extension_id}.actions.{action_id}.steps.{step_id}.fields.{target_field}: mapping is unavailable")
                    elif actual.get("type") != expected[0] and not (target == "bank_register" and target_field == "amount" and actual.get("type") == "currency"):
                        errors.append(f"extensions.{extension_id}.actions.{action_id}.steps.{step_id}.fields.{target_field}: safe-output type is incompatible")
                for field, (_, required) in REVIEW_FIELDS.get(target, {}).items():
                    if not required:
                        continue
                    source_field = spec.get("fields", {}).get(field)
                    if not source_field or not output_fields.get(source_field, {}).get("required"):
                        errors.append(f"extensions.{extension_id}.actions.{action_id}.steps.{step_id}.fields.{field}: must map from a required safe-output field")
                if target == "bank_register":
                    if binding != {"sourceCollection": "accounts", "targetType": "accounts"}:
                        errors.append(f"extensions.{extension_id}.actions.{action_id}: bank_register review requires the accounts-to-accounts action binding")
                elif target in REVIEW_FIELDS and binding is not None:
                    errors.append(f"extensions.{extension_id}.actions.{action_id}: native master-data header review must omit action.binding so the host can select a company connection")
                if index != len(action.get("steps", [])) - 1:
                    errors.append(f"extensions.{extension_id}.actions.{action_id}.steps.{step_id}: review.import must be final")

    for extension_id, extension in extensions.items():
        if extension.get("type") != "existing_page_actions":
            continue
        definition = extension.get("definition", {})
        surface = definition.get("targetPageKey")
        if not capability_required(manifest, "surfaces.contribute") or surface not in capability_list(manifest, "surfaces.contribute", "surfaces"):
            errors.append(f"extensions.{extension_id}: surface {surface!r} is not granted")
        for contribution in definition.get("actions", []):
            ref = contribution.get("action", {})
            key = (ref.get("extensionId"), ref.get("actionId"))
            if key not in actions:
                errors.append(f"extensions.{extension_id}.actions.{contribution.get('actionId')}: action reference does not exist")
                continue
            target = review_targets_by_action.get(key)
            if target and REVIEW_SURFACES.get(target) != surface:
                errors.append(f"extensions.{extension_id}.actions.{contribution.get('actionId')}: {target} review must use surface {REVIEW_SURFACES.get(target)}")
    return errors


def safe_relative_path(value: Any, field: str, errors: list[str]) -> PurePosixPath | None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field}: must be a non-empty relative path")
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts or "\\" in value:
        errors.append(f"{field}: must be a safe forward-slash relative path")
        return None
    return path


def validate(folder: Path, schema_path: Path = DEFAULT_SCHEMA) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not folder.is_dir():
        return [f"selected path is not a folder: {folder}"], warnings
    schema = load_json(schema_path, str(schema_path), errors)
    manifest = load_json(folder / "manifest.json", "manifest.json", errors)
    if schema is None or manifest is None:
        return errors, warnings
    errors.extend(schema_errors(manifest, {"$ref": "#/$defs/PluginManifest"}, schema, "manifest"))

    refs = manifest.get("extensionManifests", [])
    extensions: dict[str, dict[str, Any]] = {}
    seen_paths: set[str] = set()
    if isinstance(refs, list):
        for index, ref in enumerate(refs):
            if not isinstance(ref, dict):
                continue
            relative = safe_relative_path(ref.get("path"), f"manifest.extensionManifests[{index}].path", errors)
            if relative is None:
                continue
            if relative.as_posix() in seen_paths:
                errors.append(f"manifest.extensionManifests[{index}].path: duplicate path")
            seen_paths.add(relative.as_posix())
            extension_path = folder.joinpath(*relative.parts)
            extension = load_json(extension_path, relative.as_posix(), errors)
            if extension is None:
                continue
            errors.extend(schema_errors(extension, {"$ref": "#/$defs/ExtensionManifest"}, schema, relative.as_posix()))
            extension_id = ref.get("extensionId")
            if extension.get("extensionId") != extension_id:
                errors.append(f"{relative}.extensionId: must match root reference {extension_id!r}")
            if isinstance(extension_id, str):
                if extension_id in extensions:
                    errors.append(f"manifest.extensionManifests[{index}].extensionId: duplicate {extension_id!r}")
                extensions[extension_id] = extension
            declared_hash = ref.get("sha256")
            if declared_hash is not None:
                if not isinstance(declared_hash, str) or not SHA256.fullmatch(declared_hash):
                    errors.append(f"manifest.extensionManifests[{index}].sha256: must be a lowercase SHA-256 digest")
                else:
                    actual = hashlib.sha256(extension_path.read_bytes()).hexdigest()
                    if declared_hash != actual:
                        errors.append(f"manifest.extensionManifests[{index}].sha256: mismatch; expected {actual}")

    if not errors:
        errors.extend(bundle_errors(manifest, extensions))
    if folder.name != manifest.get("pluginId"):
        warnings.append(f"folder name {folder.name!r} differs from manifest.pluginId {manifest.get('pluginId')!r}")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a schema-v2 SPRK plugin folder")
    parser.add_argument("folder", type=Path, help="plugin folder containing manifest.json")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA, help="normative schema path")
    args = parser.parse_args()
    folder = args.folder.expanduser().resolve()
    errors, warnings = validate(folder, args.schema.expanduser().resolve())
    print(f"Validating: {folder}")
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print(f"Result: invalid ({len(errors)} error(s), {len(warnings)} warning(s))")
        return 1
    print(f"Result: valid ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
