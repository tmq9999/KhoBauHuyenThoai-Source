"""Inventory pinned VN request builders without evaluating JavaScript.

This lexical extractor is deliberately not a general JS type/dataflow analyzer.
It resolves literal arguments and adjacent standalone literal declarations;
dynamic expressions remain explicitly unresolved.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any


PINNED_SHA256 = "9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818"
GENERATOR = "kbht-vn-route-inventory"
FORMAT_VERSION = 1
ROUTE = re.compile(r"(?:logic|connector|gate)\.[A-Za-z0-9_$]+\.[A-Za-z0-9_$]+\Z")
_LEX = re.compile(
    r"(?P<space>\s+)|(?P<comment>//[^\r\n]*|/\*[\s\S]*?\*/)"
    r"|(?P<string>\"(?:\\[\s\S]|[^\"\\])*\"|'(?:\\[\s\S]|[^'\\])*')"
    r"|(?P<template>`(?:\\[\s\S]|[^`\\])*`)"
    r"|(?P<id>[A-Za-z_$][A-Za-z0-9_$]*)"
    r"|(?P<number>(?:0[xX][0-9a-fA-F]+|\d+(?:\.\d*)?(?:[eE][+-]?\d+)?))"
    r"|(?P<punct>[^\s])"
)
_REGEX = re.compile(r"/(?:\\[^\r\n]|\[(?:\\[^\r\n]|[^\]\\\r\n])*\]|[^/\\[\r\n])+/[a-z]*")
_PAIRS = {"(": ")", "{": "}", "[": "]"}
_CORE_HANDLERS = frozenset({"playerHandler", "teamHandler", "bagHandler", "pointHandler",
                             "smapHandler", "shopHandler", "friendHandler", "mailHandler"})
_EXPANSION_HANDLERS = frozenset({
    "allServerBattleHandler", "arena3v3Handler", "arenaHandler", "endlessHandler",
    "expeditionHandler", "eyeHandler", "guildBattleHandler", "guildHandler",
    "newGuildBattleHandler", "practiceHandler", "prestigeBattleHandler", "rankHandler",
    "sixExpeditionHandler", "sixPracticeHandler", "tailHandler", "videoHandler",
    "worldBossHandler", "worshipBattleHandler",
})
_CORE_BAG = frozenset({"sell", "composeItem", "composeRole"})
_EXPANSION_PLAYER = frozenset({"rollDial", "buyGetBack"})


@dataclass(frozen=True, slots=True)
class Token:
    kind: str
    value: str
    offset: int
    line: int


class InventoryError(ValueError):
    """Only fixed error codes are exposed by the CLI."""


def _tokens(source: str) -> list[Token]:
    result: list[Token] = []
    offset, line = 0, 1
    paren_context: list[bool] = []
    control_end = False
    while offset < len(source):
        match = _LEX.match(source, offset)
        if match is None:
            raise InventoryError("UNSUPPORTED_SOURCE_SYNTAX")
        kind, value = match.lastgroup, match.group()
        if value == "/" and (control_end or not result or result[-1].value in {
            "=", "(", "[", "{", ",", ";", ":", "!", "?", "return", "throw", "case", "&", "|",
        }):
            regex_match = _REGEX.match(source, offset)
            if regex_match:
                kind, value = "regex", regex_match.group()
        if kind == "punct" and value in ('"', "'", "`"):
            raise InventoryError("UNTERMINATED_LITERAL")
        if kind not in ("space", "comment"):
            after_control = False
            if kind == "punct" and value == "(":
                paren_context.append(bool(result and result[-1].value in ("if", "while", "for", "with", "switch", "catch")))
            elif kind == "punct" and value == ")" and paren_context:
                after_control = paren_context.pop()
            control_end = after_control
            result.append(Token(kind, value, offset, line))
        line += value.count("\n")
        offset += len(value)
    return result


def _literal(token: Token) -> str | None:
    if token.kind != "string" or "\\" in token.value:
        return None
    return token.value[1:-1]


def _arguments(tokens: list[Token], start: int) -> list[list[Token]] | None:
    stack = [")"]
    arguments: list[list[Token]] = []
    begin = start + 1
    for index in range(begin, len(tokens)):
        token = tokens[index]
        if token.kind != "punct":
            continue
        value = token.value
        if value in _PAIRS:
            stack.append(_PAIRS[value])
        elif value in _PAIRS.values():
            if not stack or value != stack.pop():
                return None
            if not stack:
                arguments.append(tokens[begin:index])
                return arguments
        elif value == "," and len(stack) == 1:
            arguments.append(tokens[begin:index])
            begin = index + 1
    return None


def _object_keys(tokens: list[Token]) -> list[str] | None:
    if len(tokens) < 2 or tokens[0].value != "{" or tokens[-1].value != "}":
        return None
    keys: list[str] = []
    stack: list[str] = []
    expect_key = True
    for index in range(1, len(tokens) - 1):
        token = tokens[index]
        if not stack and expect_key:
            key = token.value if token.kind == "id" else _literal(token)
            if key is None or index + 1 >= len(tokens) or tokens[index + 1].value != ":":
                return None
            keys.append(key)
            expect_key = False
        if token.kind != "punct":
            continue
        if token.value in _PAIRS:
            stack.append(_PAIRS[token.value])
        elif token.value in _PAIRS.values():
            if not stack or stack.pop() != token.value:
                return None
        elif token.value == "," and not stack:
            expect_key = True
    return keys if not stack else None


def _adjacent_route(tokens: list[Token], call_start: int, name: str) -> tuple[str, int] | None:
    # Restrict binding to `; var x = "route"; x.request...` (or block start).
    # Anything with intervening assignments, control flow or scope is unresolved.
    start = call_start - 5
    if start < 0:
        return None
    declaration = tokens[start:call_start]
    if start > 0 and tokens[start - 1].value not in (";", "{"):
        return None
    if ([token.value for token in declaration[:3]] not in
            [[keyword, name, "="] for keyword in ("var", "let", "const")]
            or declaration[-1].value != ";"):
        return None
    route = _literal(declaration[3])
    if route is None or ROUTE.fullmatch(route) is None:
        return None
    return route, declaration[0].line


def analyze(source: str) -> dict[str, list[dict[str, Any]]]:
    tokens = _tokens(source)
    calls: list[dict[str, Any]] = []
    dynamic: list[dict[str, Any]] = []
    for index in range(len(tokens) - 3):
        receiver, dot, method, opening = tokens[index:index + 4]
        if (receiver.kind != "id" or dot.value != "." or method.value != "request"
                or opening.value != "(" or method.kind != "id"):
            continue
        arguments = _arguments(tokens, index + 3)
        if arguments is None:
            raise InventoryError("MALFORMED_REQUEST_CALL")
        route, declaration_line = None, None
        binding = "LITERAL"
        if arguments and len(arguments[0]) == 1:
            route = _literal(arguments[0][0])
            if route is None and arguments[0][0].kind == "id":
                resolved = _adjacent_route(tokens, index, arguments[0][0].value)
                if resolved:
                    route, declaration_line = resolved
                    binding = "ADJACENT_LITERAL"
        if route is None:
            dynamic.append({"sourceLine": receiver.line, "reason": "NON_LITERAL_ROUTE"})
            continue
        if ROUTE.fullmatch(route) is None:
            continue
        keys = _object_keys(arguments[1]) if len(arguments) > 1 else None
        call: dict[str, Any] = {
            "route": route, "sourceLine": receiver.line, "status": "STATIC_OBSERVED",
            "routeBinding": binding, "requestKeys": keys,
            "requestShape": "OBJECT_KEYS_ONLY" if keys is not None else "DYNAMIC",
        }
        if declaration_line is not None:
            call["declarationLine"] = declaration_line
        calls.append(call)
    return {"calls": calls, "dynamicRequests": dynamic}


def inventory(source: str) -> list[dict[str, Any]]:
    return [{key: call[key] for key in ("route", "sourceLine", "status")}
            for call in analyze(source)["calls"]]


def classify(route: str) -> str:
    service, handler, method = route.split(".")
    if service in ("gate", "connector"):
        return "CORE"
    if handler == "gmHandler":
        return "DENIED_ADMIN_ONLY"
    if handler in _EXPANSION_HANDLERS or handler == "bagHandler" and method not in _CORE_BAG:
        return "EXPANSION"
    if handler == "playerHandler" and method in _EXPANSION_PLAYER:
        return "EXPANSION"
    return "CORE" if handler in _CORE_HANDLERS else "BLOCKED_EVIDENCE"


def build_manifest(raw: bytes) -> dict[str, Any]:
    digest = hashlib.sha256(raw).hexdigest()
    if digest != PINNED_SHA256:
        raise InventoryError("SOURCE_HASH_MISMATCH")
    analysis = analyze(raw.decode("utf-8"))
    routes: dict[str, dict[str, Any]] = {}
    for call in analysis["calls"]:
        name = call["route"]
        entry = routes.setdefault(name, {"route": name, "tier": classify(name), "sites": []})
        entry["sites"].append({key: value for key, value in call.items() if key != "route"})
    rows = [routes[name] for name in sorted(routes)]
    return {
        "generator": GENERATOR, "formatVersion": FORMAT_VERSION,
        "status": "STATIC_OBSERVED",
        "source": {"path": "client-recovered/src/project.js", "sha256": digest, "bytes": len(raw)},
        "extraction": "lexical requests plus adjacent standalone literal declarations; no JS execution",
        "limitations": ["Object keys are not types or response schemas.",
                        "Dynamic requests remain unresolved; templates are treated as opaque.",
                        "Tier is delivery scope, never runtime verification."],
        "summary": {"uniqueRoutes": len(rows), "callSites": len(analysis["calls"]),
                    "dynamicRequests": len(analysis["dynamicRequests"]),
                    "tiers": dict(sorted(Counter(row["tier"] for row in rows).items()))},
        "routes": rows, "dynamicRequests": analysis["dynamicRequests"],
    }


def validate_consumers(consumers: dict[str, Any], manifest: dict[str, Any]) -> None:
    if not isinstance(consumers, dict) or consumers.get("sourceSha256") != manifest["source"]["sha256"]:
        raise InventoryError("CONSUMER_SOURCE_MISMATCH")
    core = {row["route"] for row in manifest["routes"] if row["tier"] == "CORE"}
    routes, profiles = consumers.get("routes"), consumers.get("profiles")
    if not isinstance(routes, dict) or set(routes) != core or not isinstance(profiles, dict):
        raise InventoryError("CONSUMER_COVERAGE_MISMATCH")
    for name in routes.values():
        if not isinstance(name, str) or name not in profiles or not isinstance(profiles[name], dict):
            raise InventoryError("CONSUMER_PROFILE_MISSING")
        profile = profiles[name]
        lines = profile.get("lines")
        if not isinstance(lines, list) or not lines or any(type(line) is not int or line <= 0 for line in lines):
            raise InventoryError("CONSUMER_EVIDENCE_MISSING")
        for field in ("directReads", "stateReads"):
            reads = profile.get(field)
            if not isinstance(reads, list) or any(not isinstance(value, str) or not value for value in reads):
                raise InventoryError("CONSUMER_READSET_INVALID")


def _write_manifest(output: Path, data: bytes, *, check: bool, update: bool) -> None:
    if output.is_symlink():
        raise InventoryError("OUTPUT_SYMLINK")
    if output.exists():
        current = output.read_bytes()
        if current == data:
            return
        if check:
            raise InventoryError("MANIFEST_STALE")
        if not update:
            raise InventoryError("OUTPUT_EXISTS")
        try:
            previous = json.loads(current)
        except (ValueError, UnicodeError) as exc:
            raise InventoryError("OUTPUT_NOT_OWNED") from exc
        if (not isinstance(previous, dict) or previous.get("generator") != GENERATOR
                or previous.get("formatVersion") != FORMAT_VERSION
                or not isinstance(previous.get("source"), dict)
                or previous.get("source", {}).get("sha256") != PINNED_SHA256):
            raise InventoryError("OUTPUT_NOT_OWNED")
        descriptor, temporary = tempfile.mkstemp(prefix=".inventory-", dir=output.parent)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            # Never replace a concurrently changed report.
            if output.is_symlink() or output.read_bytes() != current:
                raise InventoryError("OUTPUT_CHANGED")
            os.replace(temporary, output)
        finally:
            Path(temporary).unlink(missing_ok=True)
    elif check:
        raise InventoryError("MANIFEST_MISSING")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("xb") as stream:
            stream.write(data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--consumers", type=Path, help="Validate reviewed CORE consumer coverage and provenance")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--update", action="store_true", help="Update only a manifest owned by this generator")
    args = parser.parse_args(argv)
    try:
        source = args.source.resolve(strict=True)
        output = args.output.absolute()
        if output.resolve() == source or output.exists() and os.path.samefile(source, output):
            raise InventoryError("OUTPUT_IS_SOURCE")
        if source.stat().st_size > 10 * 1024 * 1024:
            raise InventoryError("SOURCE_TOO_LARGE")
        manifest = build_manifest(source.read_bytes())
        if args.consumers is not None:
            with args.consumers.open("rb") as stream:
                content = stream.read(512 * 1024 + 1)
            if len(content) > 512 * 1024:
                raise InventoryError("CONSUMERS_TOO_LARGE")
            validate_consumers(json.loads(content), manifest)
        data = (json.dumps(manifest, ensure_ascii=True, sort_keys=True, indent=2) + "\n").encode("utf-8")
        _write_manifest(output, data, check=args.check, update=args.update)
        print(json.dumps({"status": "VERIFIED" if args.check else "GENERATED", **manifest["summary"]}))
        return 0
    except InventoryError as exc:
        print(str(exc), file=sys.stderr)
    except (OSError, UnicodeError, ValueError):
        print("INVENTORY_IO_OR_FORMAT_ERROR", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
