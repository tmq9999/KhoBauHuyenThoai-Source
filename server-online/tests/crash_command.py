"""Abruptly lose an internal command connection, never a production entrypoint."""

import os
import sys
from uuid import UUID

from kbht_server.contracts import GameCommand
from kbht_server.db.session import database_url, open_engine
from kbht_server.db.uow import CommandExecutor

schema, phase, command_id, source_id = sys.argv[1:]
engine = open_engine(database_url("test"), schema=schema)
command = GameCommand(
    command_id=UUID(command_id), account_id=UUID("00000000-0000-4000-8000-000000000001"),
    player_id=10001, server_id=1, route="internal.crash-probe", expected_version=0,
    content_version_id=UUID("00000000-0000-4000-8000-000000000010"), payload={"source": source_id},
)


def handler(work, payload):
    work.adjust_wallet("gem", -10, reason="crash-probe")
    result = work.rewards.grant(source_type="test-crash", source_id=UUID(payload["source"]),
                                items={49902: 2}, currencies={"coin": 100})
    if phase == "before-commit":
        os._exit(71)
    return result


CommandExecutor(engine, {command.route: handler}).execute(command)
os._exit(72)
