"""Read pinned APK data literals, never evaluate the recovered JavaScript."""

from functools import cache
import hashlib
import json
from pathlib import Path
import re
from typing import Any


SOURCE = Path(__file__).resolve().parents[2] / "client-recovered" / "src" / "project.js"
SOURCE_SHA256 = "9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818"
TABLES = frozenset({"roleData", "entityData", "evolutionItemData", "experienceData",
                   "consumablesData", "signInData", "soulData", "costData", "smapData"})
_TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|(?P<key>[A-Za-z_$][A-Za-z0-9_$]*)(?=\s*:)|(?P<decimal>(?<![\w.])\.[0-9]+)')


def parse_literal(text: str) -> Any:
    def normalize(match: re.Match[str]) -> str:
        if match.group("key") is not None:
            return json.dumps(match.group("key"))
        if match.group("decimal") is not None:
            return "0" + match.group("decimal")
        return match.group(0)
    return json.loads(_TOKEN.sub(normalize, text))


@cache
def _source() -> str:
    raw = SOURCE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("recovered APK data source hash mismatch")
    return raw.decode("utf-8").replace("\r\n", "\n")


@cache
def table(name: str) -> dict[int, dict[str, Any]]:
    if name not in TABLES:
        raise ValueError("unsupported APK data table")
    source = _source()
    marker = f'"{name}");\nt.exports = '
    start = source.index(marker) + len(marker)
    end = source.index("];\ncc._RF.pop();", start) + 1
    rows = parse_literal(source[start:end])
    if not isinstance(rows, list) or not rows or rows[0][0] != "kindId":
        raise ValueError("invalid APK data table")
    return {row[0]: dict(zip(rows[0], row)) for row in rows[1:] if type(row[0]) is int}
