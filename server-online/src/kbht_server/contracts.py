from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class GameCommand:
    command_id: UUID
    account_id: UUID
    player_id: int
    server_id: int
    route: str
    expected_version: int
    content_version_id: UUID
    payload: dict[str, Any]


@dataclass(frozen=True)
class CommandResult:
    command_id: UUID
    aggregate_version: int
    content_version_id: UUID
    result: dict[str, Any]
    event_ids: tuple[UUID, ...]


class DomainFailure(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message
