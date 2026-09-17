"""Keep recovery-test collection independent from the online backend package."""

from __future__ import annotations

import ast
from pathlib import Path


CLIENT_TESTS = Path(__file__).parent


def test_root_client_e2e_launchers_do_not_import_online_backend():
    """PostgreSQL-backed bridge launchers belong under ``server-online/tests``."""
    offenders: list[str] = []
    for path in CLIENT_TESTS.glob("test_*_e2e.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and (
                node.module == "kbht_server" or node.module.startswith("kbht_server.")
            ):
                offenders.append(path.name)
                break
            if isinstance(node, ast.Import) and any(
                alias.name == "kbht_server" or alias.name.startswith("kbht_server.")
                for alias in node.names
            ):
                offenders.append(path.name)
                break

    assert offenders == [], (
        "Root recovery tests must not import the PostgreSQL backend; "
        "move real E2E launchers to server-online/tests/integration: "
        + ", ".join(offenders)
    )
