"""Parse recovered data literals without evaluating the JavaScript bundle."""

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any


_TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|(?P<boolean>![01](?![\w.]))|(?P<key>[A-Za-z_$][A-Za-z0-9_$]*)(?=\s*:)|(?P<decimal>(?<![\w.])\.[0-9]+)')


def _normalize(match: re.Match[str]) -> str:
    if match.group("boolean") is not None:
        return "true" if match.group("boolean") == "!0" else "false"
    if match.group("key") is not None:
        return json.dumps(match.group("key"))
    if match.group("decimal") is not None:
        return "0" + match.group("decimal")
    return match.group(0)


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate object key")
        result[key] = value
    return result


def _validate_numbers(value: Any) -> None:
    if type(value) is float and not math.isfinite(value):
        raise ValueError("non-finite content number")
    if type(value) is int and abs(value) > 2**53 - 1:
        raise ValueError("unsafe content integer")
    if isinstance(value, dict):
        for nested in value.values():
            _validate_numbers(nested)
    elif isinstance(value, list):
        for nested in value:
            _validate_numbers(nested)


def read_table_archive(path: Path, source_sha256: str, table_name: str) -> dict[str, Any]:
    """Preserve ordered literal cells, including duplicate IDs and sparse tails.

    This is an evidence archive, not validated gameplay definitions. In contrast
    to read_table, it never chooses a winner for duplicate IDs or drops ID zero.
    """
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != source_sha256.lower():
        raise ValueError("source hash mismatch")
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9]*Data", table_name) is None:
        raise ValueError("invalid table name")
    text = raw.decode("utf-8").replace("\r\n", "\n")
    marker = f'"{table_name}");\nt.exports = '
    if text.count(marker) != 1:
        raise ValueError("missing or ambiguous table")
    start = text.index(marker) + len(marker)
    end = text.index("];\ncc._RF.pop();", start) + 1
    rows = json.loads(_TOKEN.sub(_normalize, text[start:end]), object_pairs_hook=_object)
    _validate_numbers(rows)
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], list):
        raise ValueError("invalid table shape")
    columns = rows[0]
    if (not columns or columns[0] != "kindId"
            or any(not isinstance(column, str) or not column for column in columns)
            or len(set(columns)) != len(columns)):
        raise ValueError("invalid table columns")
    for row in rows[1:]:
        if not isinstance(row, list) or not row or len(row) > len(columns):
            raise ValueError("invalid table row")
        key = row[0]
        if type(key) not in (int, float) or key != int(key) or not 0 <= key <= 2**53 - 1:
            raise ValueError("invalid kindId")
    return {"columns": columns, "rows": rows[1:]}


def read_table(path: Path, source_sha256: str, table_name: str, *,
               allow_missing_trailing: bool = False) -> dict[int, dict[str, Any]]:
    """Return unique positive-ID rows; never publish or mutate a DB."""
    archive = read_table_archive(path, source_sha256, table_name)
    columns = archive["columns"]
    result = {}
    for row in archive["rows"]:
        if len(row) != len(columns) and not allow_missing_trailing:
            raise ValueError("invalid table row")
        kind_id = row[0]
        if type(kind_id) is float and kind_id.is_integer():
            kind_id = int(kind_id)
        if type(kind_id) is not int or kind_id <= 0 or kind_id in result:
            raise ValueError("invalid or duplicate kindId")
        result[kind_id] = dict(zip(columns, row))
    return result
