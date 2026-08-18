#!/usr/bin/env python3
"""Compile restricted developer-only SPRKQL into a canonical report query AST.

SPRKQL is not runtime SQL. It accepts semantic source and field IDs, then emits
an executable ReportDefinition `data`/table-`views` fragment. The host never
executes the input text.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


class SprkQLError(ValueError):
    pass


TOKEN = re.compile(
    r"\s*(?:(?P<string>'(?:''|[^'])*')|(?P<param>:[a-z0-9][a-z0-9._-]*)|"
    r"(?P<number>-?(?:\d+(?:\.\d*)?|\.\d+))|(?P<op><=|>=|<>|!=|=|<|>)|"
    r"(?P<punct>[(),@])|(?P<ident>[a-z0-9][a-z0-9._-]*))",
    re.IGNORECASE,
)
IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
AGGREGATES = {"SUM": "sum", "COUNT": "count", "COUNT_DISTINCT": "count_distinct", "AVG": "avg", "MIN": "min", "MAX": "max"}
COMPARISONS = {"=": "eq", "!=": "ne", "<>": "ne", ">": "gt", ">=": "gte", "<": "lt", "<=": "lte"}
BANNED_WORDS = {"JOIN", "UNION", "WITH", "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "REPLACE", "TRUNCATE", "PRAGMA", "ATTACH", "DETACH", "GRANT", "REVOKE", "EXEC", "CALL"}
PHYSICAL_SOURCE_PREFIXES = {"main", "temp", "sqlite", "sqlite_master", "pg_catalog", "information_schema", "mysql", "sys"}
SUPPORTED_SOURCES = {"gl.lines": "1", "invoice.lines": "1", "bank.register": "1"}
SOURCE_DEFAULTS = {
    "gl.lines": ("ledger_line", "ledger_posted_accrual", "entry.date", "base_currency", "posted"),
    "invoice.lines": ("invoice_line", "source_document", "invoice.date", "base_currency", "issued_or_posted"),
    "bank.register": ("bank_transaction", "bank_evidence", "bank.date", "base_currency", "all"),
}


@dataclass(frozen=True)
class Tok:
    kind: str
    value: str


def tokenize(text: str) -> list[Tok]:
    if "--" in text or "/*" in text or "*/" in text or ";" in text:
        raise SprkQLError("comments and statement separators are not supported")
    tokens: list[Tok] = []
    position = 0
    while position < len(text):
        match = TOKEN.match(text, position)
        if not match:
            if text[position:].strip() == "":
                break
            raise SprkQLError(f"unsupported syntax near {text[position:position + 24]!r}")
        kind = match.lastgroup
        assert kind is not None
        value = match.group(kind)
        if kind == "ident" and value.upper() in BANNED_WORDS:
            raise SprkQLError(f"{value.upper()} is not supported")
        tokens.append(Tok(kind, value))
        position = match.end()
    return tokens


class Parser:
    def __init__(self, tokens: list[Tok]):
        self.tokens = tokens
        self.pos = 0
        self.measures: list[dict] = []

    def peek(self, value: str | None = None) -> Tok | None:
        token = self.tokens[self.pos] if self.pos < len(self.tokens) else None
        if value is None:
            return token
        return token if token and token.value.upper() == value.upper() else None

    def take(self, value: str | None = None, kind: str | None = None) -> Tok:
        token = self.peek()
        if token is None or (value is not None and token.value.upper() != value.upper()) or (kind is not None and token.kind != kind):
            expected = value or kind or "token"
            actual = "end of input" if token is None else repr(token.value)
            raise SprkQLError(f"expected {expected}, found {actual}")
        self.pos += 1
        return token

    def identifier(self) -> str:
        value = self.take(kind="ident").value.lower()
        if not IDENTIFIER.fullmatch(value):
            raise SprkQLError(f"invalid identifier {value!r}")
        return value

    def parse(self) -> dict:
        self.take("SELECT")
        selected = self.select_list()
        self.take("FROM")
        source_id = self.identifier()
        self.take("@")
        version_token = self.take()
        if version_token.kind not in {"number", "ident"}:
            raise SprkQLError("source version must follow @")
        source_version = version_token.value
        prefix = source_id.split(".", 1)[0]
        if "." not in source_id or prefix in PHYSICAL_SOURCE_PREFIXES:
            raise SprkQLError("FROM must name a versioned semantic source, not a table")
        if SUPPORTED_SOURCES.get(source_id) != source_version:
            raise SprkQLError(f"unsupported semantic source/version {source_id}@{source_version}")

        query: dict = {"select": selected}
        if self.peek("WHERE"):
            self.take("WHERE")
            query["where"] = self.expression(stop={"GROUP", "HAVING", "ORDER"})
        if self.peek("GROUP"):
            self.take("GROUP")
            self.take("BY")
            query["groupBy"] = self.identifier_list()
        if self.peek("HAVING"):
            raise SprkQLError("HAVING is not supported by the shipped report definition")
        if self.peek("ORDER"):
            self.take("ORDER")
            self.take("BY")
            query["sort"] = self.sort_list()
        if self.peek() is not None:
            raise SprkQLError(f"unexpected token {self.peek().value!r}")
        return {"source": {"sourceId": source_id, "sourceVersion": source_version}, "measures": self.measures, "query": query}

    def select_list(self) -> list[str]:
        result: list[str] = []
        while True:
            if self.peek() and self.peek().value == "*":
                raise SprkQLError("wildcard selection is not supported")
            first = self.identifier()
            if self.peek("("):
                aggregate = first.upper()
                if aggregate not in AGGREGATES:
                    raise SprkQLError(f"function {first} is not supported")
                self.take("(")
                field = self.identifier()
                self.take(")")
                self.take("AS")
                alias = self.identifier()
                self.measures.append({"measureId": alias, "field": field, "function": AGGREGATES[aggregate], "label": alias.replace("_", " ").title()})
                result.append(alias)
            else:
                result.append(first)
            if not self.peek(","):
                break
            self.take(",")
        return result

    def identifier_list(self) -> list[str]:
        values = [self.identifier()]
        while self.peek(","):
            self.take(",")
            values.append(self.identifier())
        return values

    def sort_list(self) -> list[dict]:
        result = []
        while True:
            field = self.identifier()
            direction = "asc"
            if self.peek("ASC") or self.peek("DESC"):
                direction = self.take().value.lower()
            result.append({"field": field, "direction": direction})
            if not self.peek(","):
                break
            self.take(",")
        return result

    def expression(self, stop: set[str]) -> dict:
        value = self.and_expression(stop)
        children = [value]
        while self.peek("OR"):
            self.take("OR")
            children.append(self.and_expression(stop))
        return value if len(children) == 1 else {"kind": "group", "op": "or", "children": children}

    def and_expression(self, stop: set[str]) -> dict:
        value = self.term(stop)
        children = [value]
        while self.peek("AND"):
            self.take("AND")
            children.append(self.term(stop))
        return value if len(children) == 1 else {"kind": "group", "op": "and", "children": children}

    def term(self, stop: set[str]) -> dict:
        if self.peek("("):
            self.take("(")
            value = self.expression(stop=set())
            self.take(")")
            return value
        if self.peek() is None or self.peek().value.upper() in stop:
            raise SprkQLError("expected condition")
        field = self.identifier()
        if self.peek("BETWEEN"):
            self.take("BETWEEN")
            low = self.scalar()
            self.take("AND")
            high = self.scalar()
            return {"kind": "condition", "field": field, "op": "between", "value": [low, high]}
        if self.peek("IN"):
            self.take("IN")
            self.take("(")
            values = [self.scalar()]
            while self.peek(","):
                self.take(",")
                values.append(self.scalar())
            self.take(")")
            return {"kind": "condition", "field": field, "op": "in", "value": values}
        if self.peek("CONTAINS"):
            self.take("CONTAINS")
            return {"kind": "condition", "field": field, "op": "contains", "value": self.scalar()}
        if self.peek("IS"):
            self.take("IS")
            negated = bool(self.peek("NOT"))
            if negated:
                self.take("NOT")
            self.take("EMPTY")
            return {"kind": "condition", "field": field, "op": "is_not_empty" if negated else "is_empty"}
        operator = self.take(kind="op").value
        return {"kind": "condition", "field": field, "op": COMPARISONS[operator], "value": self.scalar()}

    def scalar(self):
        token = self.take()
        if token.kind == "param":
            return {"parameter": token.value[1:].lower()}
        if token.kind == "string":
            return token.value[1:-1].replace("''", "'")
        if token.kind == "number":
            return float(token.value) if "." in token.value else int(token.value)
        if token.kind == "ident" and token.value.upper() in {"TRUE", "FALSE", "NULL"}:
            return {"TRUE": True, "FALSE": False, "NULL": None}[token.value.upper()]
        raise SprkQLError(f"expected a literal or named parameter, found {token.value!r}")


def compile_sprkql(text: str) -> dict:
    parsed = Parser(tokenize(text)).parse()
    source_id = parsed["source"]["sourceId"]
    grain, basis, date_field, amount_mode, posting_state = SOURCE_DEFAULTS[source_id]
    query = parsed["query"]

    def flatten(predicate: dict | None) -> list[dict]:
        if predicate is None:
            return []
        if predicate["kind"] == "group":
            if predicate["op"] != "and":
                raise SprkQLError("OR cannot be represented as a locked report-definition filter")
            return [item for child in predicate["children"] for item in flatten(child)]
        value = predicate.get("value")
        atoms = value if isinstance(value, list) else [value]
        if any(isinstance(atom, dict) and "parameter" in atom for atom in atoms):
            raise SprkQLError("named parameters are not supported by the shipped report definition")
        result = {"field": predicate["field"], "op": predicate["op"]}
        if "value" in predicate:
            result["value"] = value
        return [result]

    data = {
        "source": source_id,
        "grain": grain,
        "basis": {"kind": basis, "dateField": date_field, "amountMode": amount_mode, "postingState": posting_state},
    }
    filters = flatten(query.get("where"))
    if filters:
        data["requiredFilters"] = filters
    if query.get("groupBy"):
        data["allowedGroupBy"] = query["groupBy"]
    if parsed["measures"]:
        data["measures"] = parsed["measures"]
    if query.get("sort"):
        data["defaultSort"] = query["sort"]
    view = {"viewId": "default", "kind": "table", "columns": query["select"]}
    if query.get("groupBy"):
        view["groupBy"] = query["groupBy"]
    return {"sourceGrant": parsed["source"], "data": data, "views": [view]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile safe SPRKQL into an executable report data/table-views fragment.")
    parser.add_argument("file", nargs="?", type=Path, help="SPRKQL file; reads stdin when omitted")
    parser.add_argument("--compact", action="store_true", help="emit compact JSON")
    args = parser.parse_args()
    text = args.file.read_text(encoding="utf-8") if args.file else sys.stdin.read()
    try:
        value = compile_sprkql(text)
    except (OSError, SprkQLError) as exc:
        print(f"SPRKQL error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(value, indent=None if args.compact else 2, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
