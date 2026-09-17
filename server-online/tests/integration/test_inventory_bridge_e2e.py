"""Real Node bridge coverage over the loopback Pomelo/PostgreSQL boundary."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from kbht_server.adapters.pomelo_transport import PomeloInventoryServer
from kbht_server.auth import SessionService
from kbht_server.db.migrations import check_invariants
from pg_lab import ACCOUNT_IDS, CONTENT_ID
from test_fixed_boxes import MATERIALS, box_lab, draft_boxes


_ROOT = Path(__file__).resolve().parents[3]
_NODE_SCENARIO = _ROOT / "tests" / "client" / "inventory_bridge_e2e.mjs"
_ACTIONS = (
    "10000000-0000-4000-8000-000000000001",
    "10000000-0000-4000-8000-000000000002",
    "10000000-0000-4000-8000-000000000003",
    "10000000-0000-4000-8000-000000000004",
)


def _sanitized(value: bytes | str, *secrets: str) -> str:
    text = value.decode("utf-8", "replace") if isinstance(value, bytes) else value
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[redacted]")
    return text[:4000]


async def _run_node_scenario(*, url: str, token: str, bag_index: str) -> dict:
    """Run the injected-WebSocket bridge without exposing its session in argv/logs."""
    request = json.dumps({
        "url": url,
        "token": token,
        "contentVersionId": str(CONTENT_ID),
        "bagIndex": bag_index,
    }, separators=(",", ":")).encode("utf-8")
    try:
        process = await asyncio.create_subprocess_exec(
            "node", str(_NODE_SCENARIO),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as error:
        pytest.fail("could not launch Node bridge scenario: " + _sanitized(str(error), token))
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(request), timeout=20)
    except TimeoutError:
        process.kill()  # Kill only the timed-out Node child, never the test listener/database.
        stdout, stderr = await process.communicate()
        pytest.fail("Node inventory bridge scenario timed out; stderr=" + _sanitized(stderr, token))
    assert process.returncode == 0, _sanitized(stderr, token)
    try:
        return json.loads(stdout.decode("utf-8"))
    except json.JSONDecodeError as error:
        pytest.fail("Node inventory bridge emitted invalid JSON: " + _sanitized(stdout, token) + f" ({error})")


def test_node_inventory_bridge_drives_real_pomelo_and_postgres(box_lab):
    asyncio.run(_node_inventory_bridge_drives_real_pomelo_and_postgres(box_lab))


async def _node_inventory_bridge_drives_real_pomelo_and_postgres(box_lab):
    # The fixture's two boxes plus this explicitly test-labelled top-up cover the
    # dropped-response replay, ordinary open, competing-client conflict, and final open.
    box_lab.add_item(10001, 321, 2, reason="test-node-inventory-bridge-e2e")
    box_index = str(next(row["id"] for row in box_lab.items(10001) if row["kind_id"] == 321))
    token = SessionService(box_lab.engine).issue(ACCOUNT_IDS[10001])
    server = PomeloInventoryServer(box_lab.engine, host="127.0.0.1", port=0)
    await server.start()
    try:
        host, port = server.address
        result = await _run_node_scenario(
            url=f"ws://{host}:{port}/inventory", token=token, bag_index=box_index,
        )
    finally:
        await server.close()

    assert result["actions"] == list(_ACTIONS)
    assert result["staleAction"] == "10000000-0000-4000-8000-000000000005"
    assert result["lostResponseReplayed"] is True
    assert result["conflictCode"] == "CONFLICT"
    assert result["invalid"]["code"] in {"CONNECTION_CLOSED", "UNAUTHENTICATED"}
    assert result["foreign"]["code"] in {"CONNECTION_CLOSED", "FORBIDDEN"}
    final_state = result["finalState"]
    assert final_state["status"] == "ready"
    assert final_state["version"] == 6
    final_items = final_state["bag"]["items"]
    assert box_index not in final_items
    assert {
        value["kindId"]: value["count"]
        for value in final_items.values() if value is not None
    } == {kind: 24 if kind == 49902 else 4 for kind in MATERIALS}
    assert len(result["snapshots"]) >= 3  # initial, reconnect replacement, and conflict resync
    assert len(result["deltas"]) == 2
    assert len(result["rewards"]) == 2

    assert box_lab.item_quantity(10001, 321) == 0
    assert box_lab.item_quantity(10001, 49902) == 24
    assert box_lab.item_quantity(10002, 321) == 1
    for action in _ACTIONS:
        assert box_lab.receipt_count(action) == 1
        assert box_lab.reward_count(10001, "fixed-box", action) == 1
        assert len(box_lab.events(action)) == 2
    assert box_lab.receipt_count(result["staleAction"]) == 0
    assert box_lab.inventory_deltas(10001, 321) == [2, 2, -1, -1, -1, -1]
    assert not any(check_invariants(box_lab.engine).values())
