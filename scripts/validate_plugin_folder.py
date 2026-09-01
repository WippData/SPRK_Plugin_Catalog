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
WORKFLOW_DATA_ONLY_COMMANDS = {
    "records.filter", "records.sort", "records.distinct", "records.aggregate",
    "records.join", "calculate", "control.if", "control.switch", "control.stop",
}
WORKFLOW_LIST_COMMANDS = {
    "dataset.read", "records.query", "records.filter", "records.sort", "records.distinct",
    "records.aggregate", "records.join", "review.records", "control.for_each",
    "control.if", "control.switch", "control.stop", "calculate",
    "accounting.journal.preview",
}
WORKFLOW_JOURNAL_COMMITTED_EVENT = "accounting.journals.committed"
WORKFLOW_EVENT_JOURNALS_SOURCE = "$event.journals"


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


def workflow_source_command(source: Any) -> str | None:
    if not isinstance(source, str):
        return None
    match = re.fullmatch(r"\$steps\.([a-z0-9][a-z0-9._-]{0,127})\.records", source)
    return match.group(1) if match else None


def workflow_resource(extensions: dict[str, dict[str, Any]], extension_id: Any, resource_id: Any) -> dict[str, Any] | None:
    extension = extensions.get(extension_id)
    if not isinstance(extension, dict):
        return None
    return next((item for item in extension.get("resources", []) if item.get("resourceId") == resource_id and item.get("kind") == "records"), None)


def workflow_input_errors(prefix: str, item: dict[str, Any], manifest: dict[str, Any], extensions: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    input_type = item.get("type")
    multiple = item.get("multiple") is True or input_type == "multi_select"
    options = item.get("options", [])
    if item.get("multiple") is True and input_type not in {"select", "reference"}:
        errors.append(f"{prefix}.multiple: is valid only for select or reference")
    if options and input_type not in {"select", "multi_select"}:
        errors.append(f"{prefix}.options: is valid only for select or multi_select")
    if "reference" in item and input_type != "reference":
        errors.append(f"{prefix}.reference: is valid only for reference inputs")
    option_values = [option.get("value") for option in options if isinstance(option, dict)]
    if len(set(option_values)) != len(option_values):
        errors.append(f"{prefix}.options: option values must be unique")
    default = item.get("defaultValue")
    if "defaultValue" in item:
        valid = True
        if input_type in {"text", "textarea"}:
            valid = isinstance(default, str)
        elif input_type == "number":
            valid = isinstance(default, (int, float)) and not isinstance(default, bool) and math.isfinite(default)
        elif input_type == "boolean":
            valid = isinstance(default, bool)
        elif input_type == "date":
            valid = isinstance(default, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", default) is not None
        elif input_type == "date_range":
            valid = isinstance(default, dict) and set(default) == {"startDate", "endDate"} and all(isinstance(default[key], str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", default[key]) for key in default)
            valid = bool(valid and default["startDate"] <= default["endDate"])
        elif input_type == "money":
            valid = isinstance(default, dict) and set(default) == {"amount", "currency"} and isinstance(default.get("amount"), (int, float)) and not isinstance(default.get("amount"), bool) and math.isfinite(default["amount"]) and isinstance(default.get("currency"), str) and re.fullmatch(r"[A-Z]{3}", default["currency"]) is not None
        elif input_type in {"select", "multi_select"}:
            values = default if multiple else [default]
            valid = isinstance(values, list) and len(values) <= 100 and all(isinstance(value, str) and value in option_values for value in values) and len(set(values)) == len(values)
        elif input_type == "reference":
            values = default if multiple or item.get("reference", {}).get("multiple") is True else [default]
            valid = isinstance(values, list) and len(values) <= 100 and all(isinstance(value, str) and value.strip() for value in values) and len(set(values)) == len(values)
        elif input_type == "dimension_assignments":
            valid = isinstance(default, dict) and len(default) <= 100 and all(isinstance(key, str) and key and isinstance(value, str) and value for key, value in default.items())
        elif input_type == "file":
            valid = False
        if not valid:
            errors.append(f"{prefix}.defaultValue: does not match input type")
    if input_type == "reference":
        reference = item.get("reference", {})
        if reference.get("kind") == "native":
            entity = reference.get("entity")
            grants = capability_list(manifest, "data", "sprk")
            operations = next((grant.get("operations", []) for grant in grants if isinstance(grant, dict) and grant.get("entity") == entity), [])
            if not capability_required(manifest, "data") or not {"list", "get"}.issubset(set(operations)):
                errors.append(f"{prefix}.reference: native options require capabilities.data list and get for {entity}")
            if reference.get("accountFilter") is not None and entity != "accounts":
                errors.append(f"{prefix}.reference.accountFilter: is valid only for accounts")
        elif reference.get("kind") == "plugin_resource":
            if not capability_required(manifest, "records.query"):
                errors.append(f"{prefix}.reference: plugin resource options require capabilities.records.query")
            resource = workflow_resource(extensions, reference.get("extensionId"), reference.get("resourceId"))
            if resource is None or resource.get("access") == "host_only":
                errors.append(f"{prefix}.reference: must target a user-accessible same-plugin records resource")
    if input_type == "file":
        file_spec = item.get("file", {})
        requested_formats = set(file_spec.get("formats", []))
        granted_formats = set(capability_list(manifest, "files.ingest", "formats"))
        if not capability_required(manifest, "files.ingest") or not requested_formats.issubset(granted_formats):
            errors.append(f"{prefix}.file: formats require matching capabilities.files.ingest grants")
        field_ids: set[Any] = set()
        for field_index, field in enumerate(file_spec.get("fields", [])):
            field_id = field.get("fieldId")
            if field_id in field_ids:
                errors.append(f"{prefix}.file.fields[{field_index}].fieldId: duplicate")
            if field_id == "id" or (isinstance(field_id, str) and field_id.startswith("_workflow")):
                errors.append(f"{prefix}.file.fields[{field_index}].fieldId: reserved by the workflow host")
            field_ids.add(field_id)
    return errors


def workflow_expression_input_errors(value: Any, input_ids: set[str], prefix: str) -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        if value.get("kind") == "input" and value.get("input") not in input_ids:
            errors.append(f"{prefix}.input: must reference a declared workflow input")
        if "input" in value and value.get("kind") is None and value.get("input") not in input_ids:
            errors.append(f"{prefix}.input: must reference a declared workflow input")
        for key, child in value.items():
            errors.extend(workflow_expression_input_errors(child, input_ids, f"{prefix}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(workflow_expression_input_errors(child, input_ids, f"{prefix}[{index}]"))
    return errors


def validate_workflow_commands(commands: list[dict[str, Any]], prefix: str, input_ids: set[str], state: dict[str, Any], available: set[str], depth: int = 0, data_only: bool = False, for_each: bool = False, event_triggered: bool = False) -> list[str]:
    errors: list[str] = []
    if depth > 3:
        return [f"{prefix}: exceeds maximum branch depth 3"]
    state["total"] += len(commands)
    if state["total"] > 128:
        errors.append(f"{prefix}: workflow exceeds 128 total commands")
    for index, command in enumerate(commands):
        cp = f"{prefix}[{index}]"
        command_id = command.get("id")
        name = command.get("command")
        spec = command.get("with", {})
        if command_id in state["seen"]:
            errors.append(f"{cp}.id: duplicates another workflow command")
        state["seen"].add(command_id)
        if data_only and name not in WORKFLOW_DATA_ONLY_COMMANDS:
            errors.append(f"{cp}.command: nested branches may contain data-only commands only")
        if for_each and name != "calculate":
            errors.append(f"{cp}.command: control.for_each bodies may contain calculate only")
        sources: list[Any] = []
        if name == "records.join":
            sources.extend([spec.get("left"), spec.get("right")])
        elif name != "records.query" and isinstance(spec, dict) and "source" in spec:
            sources.append(spec.get("source"))
        for source in sources:
            if source == WORKFLOW_EVENT_JOURNALS_SOURCE and event_triggered:
                continue
            if source == "$context.selection.records" and not event_triggered:
                continue
            if source == "$item" and for_each:
                continue
            source_id = workflow_source_command(source)
            if source_id is None or source_id not in available:
                errors.append(f"{cp}.with: source must reference selection, the current item, or an earlier list-producing command")
        errors.extend(workflow_expression_input_errors(spec, input_ids, f"{cp}.with"))
        if name == "review.records":
            if event_triggered:
                errors.append(f"{cp}: review.records is not allowed in event workflows")
            state["reviews"] += 1
            if state["reviews"] > 1:
                errors.append(f"{cp}: only one review.records command is supported")
        if name == "dataset.read":
            input_id = spec.get("inputId")
            if event_triggered:
                errors.append(f"{cp}: dataset.read is supported only in manual workflows")
            if state.get("input_types", {}).get(input_id) != "file":
                errors.append(f"{cp}.with.inputId: must reference a declared file input")
        if name == "accounting.journal.preview":
            if event_triggered:
                errors.append(f"{cp}: accounting.journal.preview is not allowed in event workflows")
            if state["reviews"] != 1:
                errors.append(f"{cp}: accounting.journal.preview requires one earlier review.records command")
            if index != len(commands) - 1:
                errors.append(f"{cp}: accounting.journal.preview must be final")
        if name == "records.update":
            if not event_triggered:
                errors.append(f"{cp}: records.update is supported only in event workflows")
            if data_only or for_each:
                errors.append(f"{cp}: records.update is not allowed inside control flow")
            if index != len(commands) - 1:
                errors.append(f"{cp}: records.update must be final")
        if name == "control.stop" and index != len(commands) - 1:
            errors.append(f"{cp}: control.stop must be final in its block")
        if name == "control.for_each":
            if event_triggered:
                errors.append(f"{cp}: control.for_each is not allowed in event workflows")
            errors.extend(validate_workflow_commands(spec.get("commands", []), f"{cp}.with.commands", input_ids, state, set(available), depth + 1, False, True, event_triggered))
        elif name == "control.if":
            errors.extend(validate_workflow_commands(spec.get("then", []), f"{cp}.with.then", input_ids, state, set(available), depth + 1, True, False, event_triggered))
            if spec.get("else"):
                errors.extend(validate_workflow_commands(spec["else"], f"{cp}.with.else", input_ids, state, set(available), depth + 1, True, False, event_triggered))
        elif name == "control.switch":
            for case_index, case in enumerate(spec.get("cases", [])):
                errors.extend(validate_workflow_commands(case.get("commands", []), f"{cp}.with.cases[{case_index}].commands", input_ids, state, set(available), depth + 1, True, False, event_triggered))
            if spec.get("default"):
                errors.extend(validate_workflow_commands(spec["default"], f"{cp}.with.default", input_ids, state, set(available), depth + 1, True, False, event_triggered))
        if name in WORKFLOW_LIST_COMMANDS:
            available.add(command_id)
    return errors


def workflow_bundle_errors(extension_id: str, extension: dict[str, Any], manifest: dict[str, Any], extensions: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    if not capability_required(manifest, "workflows.run"):
        errors.append(f"extensions.{extension_id}: workflow requires capabilities.workflows.run.required")
    surfaces = capability_list(manifest, "surfaces.contribute", "surfaces")
    all_workflow_ids = {
        workflow.get("workflowId")
        for candidate in extensions.values()
        if candidate.get("type") == "workflow"
        for workflow in candidate.get("definition", {}).get("workflows", [])
    }
    workflow_ids: set[Any] = set()
    for workflow_index, workflow in enumerate(extension.get("definition", {}).get("workflows", [])):
        wp = f"extensions.{extension_id}.definition.workflows[{workflow_index}]"
        workflow_id = workflow.get("workflowId")
        if workflow_id in workflow_ids:
            errors.append(f"{wp}.workflowId: duplicate")
        workflow_ids.add(workflow_id)
        trigger = workflow.get("trigger", {})
        trigger_type = trigger.get("type")
        event_triggered = trigger_type == WORKFLOW_JOURNAL_COMMITTED_EVENT
        if trigger_type == "manual":
            if not capability_required(manifest, "surfaces.contribute") or "plugin_pages.header.actions" not in surfaces:
                errors.append(f"{wp}: manual workflow requires plugin_pages.header.actions")
        elif event_triggered:
            subscribed = capability_list(manifest, "events.subscribe", "events")
            if not capability_required(manifest, "events.subscribe") or WORKFLOW_JOURNAL_COMMITTED_EVENT not in subscribed:
                errors.append(f"{wp}: requires capabilities.events.subscribe for {WORKFLOW_JOURNAL_COMMITTED_EVENT}")
            if "targetExtensionId" in workflow:
                errors.append(f"{wp}.targetExtensionId: must be omitted for event workflows")
            if workflow.get("inputs"):
                errors.append(f"{wp}.inputs: must be empty for event workflows")
            filters = trigger.get("filters", {})
            for source_extension_id in filters.get("sourceExtensionIds", []):
                if extensions.get(source_extension_id, {}).get("type") != "workflow":
                    errors.append(f"{wp}.trigger.filters.sourceExtensionIds: must reference same-plugin workflow extensions")
            for source_workflow_id in filters.get("sourceWorkflowIds", []):
                if source_workflow_id not in all_workflow_ids:
                    errors.append(f"{wp}.trigger.filters.sourceWorkflowIds: must reference same-plugin workflows")
        target_id = workflow.get("targetExtensionId")
        target = extensions.get(target_id, {})
        data_source = target.get("definition", {}).get("page", {}).get("dataSource", {})
        target_resource = workflow_resource(extensions, target_id, data_source.get("resourceId"))
        if not event_triggered:
            if target.get("type") != "new_page" or data_source.get("kind") != "resource":
                errors.append(f"{wp}.targetExtensionId: must reference a same-plugin resource-backed new_page")
            elif target_resource is None or target_resource.get("access") == "host_only":
                errors.append(f"{wp}.targetExtensionId: target resource must be user-accessible records")
        input_ids: set[str] = set()
        input_types: dict[str, Any] = {}
        for input_index, item in enumerate(workflow.get("inputs", [])):
            ip = f"{wp}.inputs[{input_index}]"
            if item.get("inputId") in input_ids:
                errors.append(f"{ip}.inputId: duplicate")
            input_ids.add(item.get("inputId"))
            input_types[item.get("inputId")] = item.get("type")
            errors.extend(workflow_input_errors(ip, item, manifest, extensions))
        commands = workflow.get("commands", [])
        state: dict[str, Any] = {"seen": set(), "total": 0, "reviews": 0, "input_types": input_types}
        errors.extend(validate_workflow_commands(commands, f"{wp}.commands", input_ids, state, set(), event_triggered=event_triggered))
        inputs_by_id = {item.get("inputId"): item for item in workflow.get("inputs", [])}
        for command_index, command in enumerate(commands):
            if command.get("command") != "dataset.read":
                continue
            cp = f"{wp}.commands[{command_index}]"
            spec = command.get("with", {})
            file_input = inputs_by_id.get(spec.get("inputId"), {})
            if file_input.get("type") != "file":
                continue
            if file_input.get("required") is not True:
                errors.append(f"{cp}.with.inputId: referenced file input must be required")
            read_limit = spec.get("limit", 500)
            file_limit = file_input.get("file", {}).get("maxRows", 500)
            if isinstance(read_limit, int) and isinstance(file_limit, int) and file_limit > read_limit:
                errors.append(f"{cp}.with.limit: must be at least the referenced file input maxRows")
        for command_index, command in enumerate(commands):
            cp = f"{wp}.commands[{command_index}]"
            if command.get("command") != "records.query":
                continue
            spec = command.get("with", {})
            if "resource" in spec:
                ref = spec.get("resource", {})
                resource = workflow_resource(extensions, ref.get("extensionId"), ref.get("resourceId"))
                if not capability_required(manifest, "records.query"):
                    errors.append(f"{cp}: plugin records query requires capabilities.records.query")
                if extensions.get(ref.get("extensionId"), {}).get("type") != "new_page" or resource is None or resource.get("access") == "host_only":
                    errors.append(f"{cp}: query must target a user-accessible same-plugin new_page records resource")
                elif not event_triggered and (ref.get("extensionId") != target_id or ref.get("resourceId") != data_source.get("resourceId")):
                    errors.append(f"{cp}: manual workflow may query only its target page resource")
            else:
                entity = spec.get("entity")
                if event_triggered:
                    errors.append(f"{cp}: event workflows may query only same-plugin resources")
                grants = capability_list(manifest, "data", "sprk")
                allowed = any(isinstance(grant, dict) and grant.get("entity") == entity and "list" in grant.get("operations", []) for grant in grants)
                if not capability_required(manifest, "data") or not allowed:
                    errors.append(f"{cp}: native query is not granted by capabilities.data")
        if any(command.get("command") == "accounting.journal.preview" for command in commands) and not capability_required(manifest, "accounting.journal.propose"):
            errors.append(f"{wp}: accounting.journal.preview requires capabilities.accounting.journal.propose")
        for command_index, command in enumerate(commands):
            if command.get("command") != "records.update":
                continue
            cp = f"{wp}.commands[{command_index}]"
            spec = command.get("with", {})
            ref = spec.get("resource", {})
            resource = workflow_resource(extensions, ref.get("extensionId"), ref.get("resourceId"))
            if not capability_required(manifest, "records.write"):
                errors.append(f"{cp}: records.update requires capabilities.records.write")
            if extensions.get(ref.get("extensionId"), {}).get("type") != "new_page" or resource is None or resource.get("access") == "host_only":
                errors.append(f"{cp}: records.update must target a user-accessible same-plugin new_page records resource")
    return errors


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
        elif ext_type == "workflow":
            errors.extend(workflow_bundle_errors(extension_id, extension, manifest, extensions))
        elif ext_type == "document_template":
            if not capability_required(manifest, "documents.render"):
                errors.append(f"extensions.{extension_id}: document template requires capabilities.documents.render.required")
        elif ext_type == "accounting_schedule" and definition.get("definitionVersion") == "2":
            for capability in ("accounting.schedules.manage", "accounting.journal.propose"):
                if not capability_required(manifest, capability):
                    errors.append(f"extensions.{extension_id}: v2 accounting schedule requires capabilities.{capability}.required")

            fields = {
                field.get("fieldId"): field
                for field in definition.get("fields", [])
                if isinstance(field, dict)
            }
            source_reference = fields.get("sourceReference")
            if not source_reference or source_reference.get("dataType") != "string" or source_reference.get("required") is not True:
                errors.append(f"extensions.{extension_id}: v2 accounting schedule requires a required string sourceReference field")

            calculation = definition.get("calculation", {})
            source_types = {
                "amountSource": {"currency", "number"},
                "startDateSource": {"date"},
                "periodCountSource": {"number"},
                "openingRecognizedAmountSource": {"currency", "number"},
                "openingRecognizedThroughSource": {"date"},
                "salvageValueSource": {"currency", "number"},
            }
            for source_key, allowed_types in source_types.items():
                field_id = calculation.get(source_key)
                if source_key == "salvageValueSource" and field_id is None:
                    continue
                field = fields.get(field_id)
                if field is None:
                    errors.append(f"extensions.{extension_id}.definition.calculation.{source_key}: must reference a declared field")
                elif field.get("dataType") not in allowed_types:
                    errors.append(f"extensions.{extension_id}.definition.calculation.{source_key}: field type must be one of {sorted(allowed_types)!r}")

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
    proposal_mappings_by_action: dict[tuple[str, str], dict[str, Any]] = {}
    legacy_delta_resources_by_action: dict[tuple[str, str], dict[str, Any]] = {}
    for (extension_id, action_id), action in actions.items():
        action_extension = extensions[extension_id]
        mapping_list = action_extension.get("definition", {}).get("fieldMappings", [])
        mappings = {item.get("mappingId"): item for item in mapping_list if isinstance(item, dict)}
        if len(mappings) != len(mapping_list):
            errors.append(f"extensions.{extension_id}.definition.fieldMappings: mappingId values must be unique")
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
            elif command == "review.propose":
                mapping = mappings.get(spec.get("mappingId"))
                if mapping is None:
                    errors.append(f"extensions.{extension_id}.actions.{action_id}.steps.{step_id}: field mapping does not exist")
                    continue
                proposal_mappings_by_action[(extension_id, action_id)] = mapping
                target = mapping.get("target", {})
                grants = [grant.get("target") for grant in capability_list(manifest, "review", "proposals") if isinstance(grant, dict)]
                if not capability_required(manifest, "review") or target not in grants:
                    errors.append(f"extensions.{extension_id}.actions.{action_id}.steps.{step_id}: proposal target is not granted exactly")
                source = mapping.get("source", {})
                fields = mapping.get("fields", {})
                if source.get("kind") == "safe_output":
                    parts = source_parts(source.get("path", ""))
                    output = safe_outputs.get(parts) if parts else None
                    if output is None:
                        errors.append(f"extensions.{extension_id}.actions.{action_id}.steps.{step_id}: proposal source must reference an earlier safe output")
                    else:
                        output_fields = output.get("fields", {})
                        for target_field, mapping_value in fields.items():
                            source_field = mapping_value.get("from") if isinstance(mapping_value, dict) else None
                            if source_field is None:
                                continue
                            if source_field not in output_fields:
                                errors.append(f"extensions.{extension_id}.definition.fieldMappings.{mapping.get('mappingId')}.fields.{target_field}: source field is not in the safe output")
                elif source.get("kind") == "plugin_selection":
                    source_extension = extensions.get(source.get("extensionId"), {})
                    source_resource = next((item for item in source_extension.get("resources", []) if item.get("resourceId") == source.get("resourceId") and item.get("kind") == "records"), None)
                    if source_extension.get("type") != "new_page" or source_resource is None:
                        errors.append(f"extensions.{extension_id}.definition.fieldMappings.{mapping.get('mappingId')}: plugin_selection source must reference a new-page records resource")
                    else:
                        source_fields = {item.get("fieldId") for item in source_resource.get("recordSchema", {}).get("fields", [])}
                        for target_field, mapping_value in fields.items():
                            source_field = mapping_value.get("from") if isinstance(mapping_value, dict) else None
                            if source_field is None:
                                continue
                            if source_field not in source_fields:
                                errors.append(f"extensions.{extension_id}.definition.fieldMappings.{mapping.get('mappingId')}.fields.{target_field}: source field is not in the plugin resource")
                        writeback = mapping.get("writeback", {})
                        for field in (writeback.get("targetIdField"), writeback.get("operationField")):
                            if field and field not in source_fields:
                                errors.append(f"extensions.{extension_id}.definition.fieldMappings.{mapping.get('mappingId')}.writeback: field {field!r} is not in the source resource")
                if target.get("kind") == "plugin_resource":
                    target_extension = extensions.get(target.get("extensionId"), {})
                    target_resource = next((item for item in target_extension.get("resources", []) if item.get("resourceId") == target.get("resourceId") and item.get("kind") == "records"), None)
                    if target_resource is None:
                        errors.append(f"extensions.{extension_id}.definition.fieldMappings.{mapping.get('mappingId')}: plugin_resource target does not exist")
                    else:
                        target_fields = {item.get("fieldId") for item in target_resource.get("recordSchema", {}).get("fields", [])}
                        delta = mapping.get("delta", {})
                        for field in list(fields) + [delta.get("identityField"), delta.get("inactiveField")]:
                            if field and field not in target_fields:
                                errors.append(f"extensions.{extension_id}.definition.fieldMappings.{mapping.get('mappingId')}: target field {field!r} is not in the plugin resource")
                if index != len(action.get("steps", [])) - 1:
                    errors.append(f"extensions.{extension_id}.actions.{action_id}.steps.{step_id}: review.propose must be final")
            elif command == "resource.apply_delta":
                legacy_delta_resources_by_action[(extension_id, action_id)] = spec.get("resource", {})

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

    for extension_id, extension in extensions.items():
        if extension.get("type") != "new_page":
            continue
        definition = extension.get("definition", {})
        resource_id = definition.get("page", {}).get("dataSource", {}).get("resourceId")
        contributions = definition.get("pageActions", []) + definition.get("rowActions", [])
        if any(contribution.get("kind") == "run_action" for contribution in contributions):
            surfaces = capability_list(manifest, "surfaces.contribute", "surfaces")
            if not capability_required(manifest, "surfaces.contribute") or "plugin_pages.header.actions" not in surfaces:
                errors.append(f"extensions.{extension_id}: plugin page run_action requires plugin_pages.header.actions")
        for contribution in contributions:
            if contribution.get("kind") != "run_action":
                continue
            ref = contribution.get("action", {})
            key = (ref.get("extensionId"), ref.get("actionId"))
            if key not in actions:
                errors.append(f"extensions.{extension_id}.actions.{contribution.get('actionId')}: action reference does not exist")
                continue
            mapping = proposal_mappings_by_action.get(key, {})
            legacy_delta_resource = legacy_delta_resources_by_action.get(key, {})
            source = mapping.get("source", {})
            target = mapping.get("target", {})
            source_matches = source.get("kind") == "plugin_selection" and source.get("extensionId") == extension_id and source.get("resourceId") == resource_id
            target_matches = source.get("kind") == "safe_output" and target.get("kind") == "plugin_resource" and target.get("extensionId") == extension_id and target.get("resourceId") == resource_id
            legacy_delta_matches = legacy_delta_resource.get("extensionId") == extension_id and legacy_delta_resource.get("resourceId") == resource_id
            if not source_matches and not target_matches and not legacy_delta_matches:
                errors.append(f"extensions.{extension_id}.actions.{contribution.get('actionId')}: run_action mapping must read from or write to this page resource")
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
