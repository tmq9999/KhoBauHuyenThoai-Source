"""Grant caller-authorized rewards exactly once per recipient and source."""

import hashlib
import json
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import select

from kbht_server.contracts import DomainFailure
from kbht_server.db.repositories import label, positive_int
from kbht_server.db.schema import reward_currencies, reward_grants, reward_items
from .boxes import use_fixed_box

if TYPE_CHECKING:
    from kbht_server.db.uow import UnitOfWork


class RewardService:
    def __init__(self, work: "UnitOfWork"):
        self.work = work

    def grant(self, *, source_type: str, source_id: UUID, items: dict[int, int] | None = None,
              currencies: dict[str, int] | None = None) -> dict:
        label(source_type, 64)
        if type(source_id) is not UUID:
            raise DomainFailure("VALIDATION_ERROR", "Invalid reward source")
        items = {} if items is None else items
        currencies = {} if currencies is None else currencies
        if type(items) is not dict or type(currencies) is not dict or not (items or currencies):
            raise DomainFailure("VALIDATION_ERROR", "Reward must contain item or currency amounts")
        if len(items) + len(currencies) > 100:
            raise DomainFailure("LIMIT_REACHED", "Reward has too many asset kinds")
        for kind_id, quantity in items.items():
            positive_int(kind_id)
            positive_int(quantity)
        for currency, quantity in currencies.items():
            label(currency, 32)
            positive_int(quantity)
        item_lines = [{"kind_id": kind_id, "quantity": quantity} for kind_id, quantity in sorted(items.items())]
        currency_lines = dict(sorted(currencies.items()))
        payload = {"items": item_lines, "currencies": currency_lines,
                   "content_version_id": str(self.work.command.content_version_id)}
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        saved = self.work.connection.execute(select(reward_grants).where(
            reward_grants.c.player_id == self.work.command.player_id,
            reward_grants.c.source_type == source_type, reward_grants.c.source_id == source_id,
        )).mappings().one_or_none()
        if saved:
            if saved["payload_hash"] != digest:
                raise DomainFailure("CONFLICT", "Reward source has different content")
            return saved["result_json"]
        # Validate all definitions before starting the grant. No gameplay input chooses loot here.
        for line in item_lines:
            self.work.inventory.definition(line["kind_id"])
        grant_id = uuid4()
        result = {"grant_id": str(grant_id), "items": item_lines, "currencies": currency_lines}
        self.work.connection.execute(reward_grants.insert().values(
            id=grant_id, player_id=self.work.command.player_id, command_id=self.work.command.command_id,
            content_version_id=self.work.command.content_version_id, source_type=source_type,
            source_id=source_id, payload_hash=digest, result_json=result,
        ))
        for line in item_lines:
            self.work.inventory.add(line["kind_id"], line["quantity"], reason=f"reward:{grant_id}",
                                    source_type="reward", source_id=source_id, reward_grant_id=grant_id)
            self.work.connection.execute(reward_items.insert().values(
                grant_id=grant_id, content_version_id=self.work.command.content_version_id, **line,
            ))
        for currency, quantity in currency_lines.items():
            self.work.adjust_wallet(currency, quantity, reason=f"reward:{grant_id}")
            self.work.connection.execute(reward_currencies.insert().values(
                grant_id=grant_id, currency=currency, quantity=quantity,
            ))
        self.work.emit("reward.granted", {"source_type": source_type, "source_id": str(source_id), **result})
        return result
