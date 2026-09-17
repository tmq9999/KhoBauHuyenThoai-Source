from dataclasses import asdict
from uuid import uuid4

import pytest

from kbht_server.contracts import DomainFailure
from kbht_server.db.uow import CommandExecutor
from pg_lab import ACCOUNT_IDS
from purchase_fixture import purchase


def adapter_type():
    import kbht_server
    from importlib.util import find_spec
    assert find_spec("kbht_server.adapters") is not None, "Online command adapter is missing"
    from kbht_server.adapters.commands import CommandAdapter
    return CommandAdapter


def request(lab):
    command = lab.purchase_command(player_id=10001, cost_gem=10, reward_coin=300, key="adapter")
    envelope = asdict(command)
    envelope.pop("account_id")
    for key in ("command_id", "content_version_id"):
        envelope[key] = str(envelope[key])
    return envelope


def test_command_adapter_replay_and_ownership(pg_lab):
    adapter = adapter_type()(CommandExecutor(pg_lab.engine, {"internal.purchase": purchase}), {"internal.purchase"})
    envelope = request(pg_lab)
    result = adapter.execute(ACCOUNT_IDS[10001], envelope)
    assert result == adapter.execute(ACCOUNT_IDS[10001], envelope)
    assert result["result"] == {"gem": 40, "coin": 300}
    assert pg_lab.wallet(10001, "gem") == 40
    with pytest.raises(DomainFailure) as error:
        adapter.execute(ACCOUNT_IDS[10002], envelope)
    assert error.value.code == "FORBIDDEN"


@pytest.mark.parametrize("field,value", [("player_id", True), ("expected_version", -1), ("player_id", 9007199254740992), ("payload", []), ("command_id", "bad"), ("account_id", str(uuid4()))])
def test_invalid_wire_envelope_has_no_effect(pg_lab, field, value):
    adapter = adapter_type()(CommandExecutor(pg_lab.engine, {"internal.purchase": purchase}), {"internal.purchase"})
    envelope = request(pg_lab)
    envelope[field] = value
    with pytest.raises(DomainFailure) as error:
        adapter.execute(ACCOUNT_IDS[10001], envelope)
    assert error.value.code == "VALIDATION_ERROR"
    assert pg_lab.wallet(10001, "gem") == 50


def test_adapter_default_denies_internal_and_admin_routes(pg_lab):
    adapter = adapter_type()(CommandExecutor(pg_lab.engine, {"internal.purchase": purchase}))
    with pytest.raises(DomainFailure) as error:
        adapter.execute(ACCOUNT_IDS[10001], request(pg_lab))
    assert error.value.code == "NOT_IMPLEMENTED"
    assert pg_lab.wallet(10001, "gem") == 50
