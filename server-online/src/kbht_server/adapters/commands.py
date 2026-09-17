from __future__ import annotations

from uuid import UUID
from typing import Any

from kbht_server.contracts import DomainFailure, GameCommand
from .native_inventory import NativeInventoryAdapter


class CommandAdapter:
    """Validate a native envelope before handing it to the transactional executor."""

    def __init__(self, executor: Any, routes: set[str] | None = None):
        self.executor = executor
        self.routes = frozenset(routes or ())

    def execute(self, account_id: UUID, envelope: dict[str, Any]) -> dict[str, Any]:
        try:
            if not isinstance(envelope, dict) or set(envelope) != {
                "command_id", "player_id", "server_id", "route", "expected_version",
                "content_version_id", "payload",
            }:
                raise ValueError
            command = GameCommand(
                command_id=UUID(str(envelope["command_id"])),
                account_id=account_id,
                player_id=envelope["player_id"],
                server_id=envelope["server_id"],
                route=envelope["route"],
                expected_version=envelope["expected_version"],
                content_version_id=UUID(str(envelope["content_version_id"])),
                payload=envelope["payload"],
            )
            if (not isinstance(account_id, UUID)
                    or type(command.player_id) is not int or not 0 < command.player_id <= 9007199254740991
                    or type(command.server_id) is not int or not 0 < command.server_id <= 2147483647
                    or type(command.expected_version) is not int or not 0 <= command.expected_version < 2147483647
                    or not isinstance(command.route, str) or not isinstance(command.payload, dict)):
                raise ValueError
            if command.route not in self.routes:
                raise DomainFailure("NOT_IMPLEMENTED", "Route is not registered")
        except DomainFailure:
            raise
        except (TypeError, ValueError, AttributeError):
            raise DomainFailure("VALIDATION_ERROR", "Invalid command envelope") from None
        result = self.executor.execute(command)
        return {"commandId": str(result.command_id), "version": result.aggregate_version,
                "contentVersionId": str(result.content_version_id), "result": result.result,
                "eventIds": [str(value) for value in result.event_ids]}
