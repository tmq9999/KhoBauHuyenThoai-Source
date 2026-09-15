#!/usr/bin/env python3
"""Statically index selected Cocos Creator settings fields without executing JS."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


class ParseError(ValueError):
    """The input is outside the conservative supported settings syntax."""


_ASSIGNMENT = re.compile(r"\bwindow\s*\.\s*_CCSettings\s*=")
_JS_STRING = r"(?P<q>['\"])(?P<body>(?:\\.|(?!\1).)*)\1"


def _skip_string(text: str, start: int) -> int:
    quote = text[start]
    pos = start + 1
    while pos < len(text):
        if text[pos] == "\\":
            pos += 2
        elif text[pos] == quote:
            return pos + 1
        else:
            pos += 1
    raise ParseError("unterminated JavaScript string")


def _balanced(text: str, start: int) -> tuple[str, int]:
    pairs = {"{": "}", "[": "]"}
    if start >= len(text) or text[start] not in pairs:
        raise ParseError("expected object or array")
    stack = [pairs[text[start]]]
    pos = start + 1
    while pos < len(text):
        char = text[pos]
        if char in "'\"":
            pos = _skip_string(text, pos)
            continue
        if char == "/" and pos + 1 < len(text) and text[pos + 1] == "/":
            newline = text.find("\n", pos + 2)
            pos = len(text) if newline < 0 else newline + 1
            continue
        if char == "/" and pos + 1 < len(text) and text[pos + 1] == "*":
            end = text.find("*/", pos + 2)
            if end < 0:
                raise ParseError("unterminated JavaScript comment")
            pos = end + 2
            continue
        if char in pairs:
            stack.append(pairs[char])
        elif char in "}]":
            if char != stack[-1]:
                raise ParseError("mismatched JavaScript container")
            stack.pop()
            if not stack:
                return text[start : pos + 1], pos + 1
        pos += 1
    raise ParseError("unterminated JavaScript container")


def _decode_string(raw: str) -> str:
    if len(raw) < 2 or raw[0] not in "'\"" or raw[-1] != raw[0]:
        raise ParseError("expected JavaScript string literal")
    body = raw[1:-1]
    output: list[str] = []
    pos = 0
    escapes = {"b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t", "v": "\v", "0": "\0"}
    while pos < len(body):
        if body[pos] != "\\":
            output.append(body[pos])
            pos += 1
            continue
        pos += 1
        if pos >= len(body):
            raise ParseError("truncated JavaScript escape")
        code = body[pos]
        if code in "\\/'\"":
            output.append(code)
            pos += 1
        elif code in escapes:
            output.append(escapes[code])
            pos += 1
        elif code == "x" and re.fullmatch(r"[0-9A-Fa-f]{2}", body[pos + 1 : pos + 3]):
            output.append(chr(int(body[pos + 1 : pos + 3], 16)))
            pos += 3
        elif code == "u" and re.fullmatch(r"[0-9A-Fa-f]{4}", body[pos + 1 : pos + 5]):
            output.append(chr(int(body[pos + 1 : pos + 5], 16)))
            pos += 5
        else:
            raise ParseError(f"unsupported JavaScript escape: \\{code}")
    return "".join(output)


def _property_value(settings: str, name: str) -> str | None:
    """Return the first matching property; nested/repeated names are not disambiguated."""
    match = re.search(rf"(?<![\w$]){re.escape(name)}\s*:\s*", settings)
    if not match:
        return None
    pos = match.end()
    if pos >= len(settings):
        raise ParseError(f"missing value for {name}")
    if settings[pos] in "{[":
        return _balanced(settings, pos)[0]
    if settings[pos] in "'\"":
        end = _skip_string(settings, pos)
        return settings[pos:end]
    raise ParseError(f"unsupported value syntax for {name}")


def _strings(container: str) -> list[str]:
    values: list[str] = []
    pos = 1
    while pos < len(container) - 1:
        if container[pos] in "'\"":
            end = _skip_string(container, pos)
            values.append(_decode_string(container[pos:end]))
            pos = end
        else:
            pos += 1
    return values


def _scenes(settings: str) -> list[dict[str, Any]]:
    raw = _property_value(settings, "scenes")
    if raw is None:
        return []
    scenes: list[dict[str, Any]] = []
    for match in re.finditer(r"\{[^{}]*\}", raw, re.DOTALL):
        item = match.group(0)
        url_raw = _property_value(item, "url")
        uuid_raw = _property_value(item, "uuid")
        if url_raw is None or uuid_raw is None:
            continue
        scenes.append(
            {"index": len(scenes), "url": _decode_string(url_raw), "uuid": _decode_string(uuid_raw)}
        )
    return scenes


def _raw_assets(settings: str) -> list[dict[str, str]]:
    raw_assets = _property_value(settings, "rawAssets")
    if raw_assets is None:
        return []
    assets = _property_value(raw_assets, "assets")
    if assets is None:
        return []
    entry = re.compile(
        rf"{_JS_STRING}\s*:\s*\[\s*(?P<pq>['\"])(?P<path>(?:\\.|(?!\3).)*)\3",
        re.DOTALL,
    )
    output = []
    for match in entry.finditer(assets):
        output.append(
            {
                "id": _decode_string(match.group("q") + match.group("body") + match.group("q")),
                "path": _decode_string(match.group("pq") + match.group("path") + match.group("pq")),
            }
        )
    return output


def index_settings(text: str, *, source_name: str) -> dict[str, Any]:
    assignment = _ASSIGNMENT.search(text)
    if assignment is None:
        raise ParseError("window._CCSettings assignment not found")
    start = assignment.end()
    while start < len(text) and text[start].isspace():
        start += 1
    settings, _ = _balanced(text, start)

    launch_raw = _property_value(settings, "launchScene")
    orientation_raw = _property_value(settings, "orientation")
    scenes = _scenes(settings)
    raw_assets = _raw_assets(settings)
    js_raw = _property_value(settings, "jsList")
    js_list = _strings(js_raw) if js_raw is not None else []
    encoded = text.encode("utf-8")
    return {
        "schemaVersion": 1,
        "source": {
            "name": Path(source_name).name,
            "bytes": len(encoded),
            "sha256": hashlib.sha256(encoded).hexdigest(),
        },
        "launchScene": _decode_string(launch_raw) if launch_raw is not None else None,
        "orientation": _decode_string(orientation_raw) if orientation_raw is not None else None,
        "counts": {"scenes": len(scenes), "rawAssets": len(raw_assets), "jsList": len(js_list)},
        "scenes": scenes,
        "rawAssets": raw_assets,
        "jsList": js_list,
    }


def _absolute_path(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _is_link_or_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return path.is_symlink() or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def _has_link_ancestor(path: Path) -> bool:
    absolute = _absolute_path(path)
    return any(_is_link_or_reparse(candidate) for candidate in (absolute, *absolute.parents))


def _under(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def validate_output_paths(input_path: Path, json_output: Path, csv_output: Path) -> tuple[Path, Path]:
    source = _absolute_path(input_path)
    json_target = _absolute_path(json_output)
    csv_target = _absolute_path(csv_output)
    if any(_has_link_ancestor(path) for path in (source, json_target, csv_target)):
        raise ValueError("input/output must not use symlink or reparse ancestry")
    if json_target in (source, csv_target) or csv_target == source:
        raise ValueError("outputs must be distinct from input and each other")
    approved = (_absolute_path(ROOT / "docs" / "reverse-engineering"), _absolute_path(ROOT / "work" / "apk-vn"))
    if not all(any(_under(target, directory) for directory in approved) for target in (json_target, csv_target)):
        raise ValueError("output must be under docs/reverse-engineering or work/apk-vn")
    apk_tree = _absolute_path(ROOT / "APK")
    baseline = _absolute_path(ROOT / "work" / "apk-vn" / "20260914T180000Z")
    if any(_under(target, apk_tree) for target in (json_target, csv_target)):
        raise ValueError("output must not be inside the APK tree")
    if any(_under(target, baseline) for target in (json_target, csv_target)):
        raise ValueError("output must not be inside the APK baseline")
    if json_target.exists() or csv_target.exists():
        raise ValueError("output exists; refusing to clobber")
    return json_target, csv_target


def _write_outputs(index: dict[str, Any], json_output: Path, csv_output: Path) -> None:
    json_output.parent.mkdir(parents=True, exist_ok=True)
    csv_output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with json_output.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(index, ensure_ascii=False, indent=2) + "\n")
        with csv_output.open("x", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["index", "url", "uuid"], lineterminator="\n")
            writer.writeheader()
            writer.writerows(index["scenes"])
    except FileExistsError as exc:
        raise ValueError("output exists; refusing to clobber") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--json-output", required=True, type=Path)
    parser.add_argument("--scene-csv-output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        json_output, csv_output = validate_output_paths(args.input, args.json_output, args.scene_csv_output)
        text = args.input.read_text(encoding="utf-8")
        index = index_settings(text, source_name=args.input.name)
        _write_outputs(index, json_output, csv_output)
    except (OSError, UnicodeError, ParseError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(json.dumps({"source": index["source"], "counts": index["counts"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
