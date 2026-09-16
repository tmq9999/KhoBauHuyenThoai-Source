"""Internal ledger exercise. Not a game price rule or exposed player route."""

from kbht_server.contracts import DomainFailure
from kbht_server.db.uow import CommandExecutor


def purchase(work, payload):
    if set(payload) != {"cost_gem", "reward_coin"} or any(
        type(value) is not int or not 0 < value <= 9_007_199_254_740_991
        for value in payload.values()
    ):
        raise DomainFailure("VALIDATION_ERROR", "Invalid test purchase")
    gem = work.adjust_wallet("gem", -payload["cost_gem"], reason="test-purchase")
    coin = work.adjust_wallet("coin", payload["reward_coin"], reason="test-purchase")
    work.emit("test.purchased", {"coin": coin})
    return {"gem": gem, "coin": coin}


def execute_purchase(engine, command, *, cost_gem, reward_coin):
    assert command.payload == {"cost_gem": cost_gem, "reward_coin": reward_coin}
    return CommandExecutor(engine, {"internal.purchase": purchase}).execute(command)
