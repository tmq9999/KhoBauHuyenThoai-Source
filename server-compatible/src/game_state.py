"""Durable local account and player state for the recovered game-entry flow."""

from __future__ import annotations

import base64
import copy
import datetime as _dt
import gzip
import hashlib
import hmac
import json
import math
import secrets
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Callable

from game_content import table
from game_rules import (
    ATTR_KEYS, FIRST_MAP_RULES, ROLE_LEVEL_EXPERIENCE, STAR_GROWTH, SUPPORTED_ROLE_IDS,
    advance_player, advance_role, equipment_attrs, player_supported, role_growth,
    role_max_level, role_power, role_supported,
)


_FIRST_RECRUIT_ROLES: dict[str, dict[str, Any]] = {
    "100201": {
        "kindId": 100201, "level": 1, "star": 1, "awakeLevel": 0,
        "experience": 0, "nextLevelExp": 25, "power": 0, "mp": 0,
        "attr": {"hp": 1752, "atk": 127, "def": 156, "mdef": 156, "hit": 100, "dodge": 28, "crit": 40},
        "initAttr": {"hp": 1201, "atk": 47, "def": 105, "mdef": 105, "hit": 100, "dodge": 0, "crit": 0},
        "equipmentsAttr": {"hp": 551, "atk": 80, "def": 51, "mdef": 51, "hit": 0, "dodge": 28, "crit": 40},
        "equipments": {f"evlItem_{i}": {"kindId": 30000 + i * 100 + 1, "level": 1} for i in range(1, 7)},
        "skills": {"100201": {"kindId": 100201, "level": 1}}, "awakeSkills": {}, "awakeRateIncreaseTimes": 0,
    },
    "100301": {
        "kindId": 100301, "level": 1, "star": 1, "awakeLevel": 0,
        "experience": 0, "nextLevelExp": 25, "power": 0, "mp": 0,
        "attr": {"hp": 1372, "atk": 181, "def": 147, "mdef": 147, "hit": 100, "dodge": 28, "crit": 40},
        "initAttr": {"hp": 821, "atk": 101, "def": 96, "mdef": 96, "hit": 100, "dodge": 0, "crit": 0},
        "equipmentsAttr": {"hp": 551, "atk": 80, "def": 51, "mdef": 51, "hit": 0, "dodge": 28, "crit": 40},
        "equipments": {f"evlItem_{i}": {"kindId": 30000 + i * 100 + 1, "level": 1} for i in range(1, 7)},
        "skills": {"100301": {"kindId": 100301, "level": 1}}, "awakeSkills": {}, "awakeRateIncreaseTimes": 0,
    },
}

# Local compatibility policy: enough for a lab playthrough, finite so an
# abandoned client-local simulation cannot block the player permanently.
_SMAP_PENDING_TTL_SECONDS = 30 * 60

# UI reads these before any corresponding route is called (16133, 17126,
# 53430, 40349, 22017). Missing counters are not the same as missing services.
_SNAPSHOT_DEFAULTS = {
    "vip": {"buyCoinTimes": 0, "buyActionPointTimes": 0, "buySkillPointTimes": 0,
            "buyMapType5Times": 0, "resetSmapTimesTimesMap": {}},
    "point": {"gemTimes": 0},
    "friend": {"actionPointReceiveTimes": 0},
}


def encode_player(player: dict[str, Any]) -> str:
    raw = json.dumps(player, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(gzip.compress(raw, mtime=0)).decode("ascii")


class PlayerStore:
    """SQLite-backed accounts and one player per account/server."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA busy_timeout=5000")
        self.lock = threading.RLock()
        self.tokens: dict[str, tuple[str, str]] = {}
        with self.lock:
            self.db.executescript(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    uid TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE,
                    salt BLOB NOT NULL, digest BLOB NOT NULL
                );
                CREATE TABLE IF NOT EXISTS players (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT NOT NULL REFERENCES accounts(uid),
                    server_id INTEGER NOT NULL, payload TEXT NOT NULL,
                    UNIQUE(uid, server_id)
                );
                CREATE TABLE IF NOT EXISTS smap_pending (
                    player_id INTEGER PRIMARY KEY REFERENCES players(id) ON DELETE CASCADE,
                    uid TEXT NOT NULL, server_id INTEGER NOT NULL,
                    smap_id INTEGER NOT NULL, team_indices TEXT NOT NULL,
                    expires_at INTEGER NOT NULL
                );
                """
            )
            self.db.commit()

    def close(self) -> None:
        with self.lock:
            self.db.close()

    def _new_account(self, name: str, password: str) -> tuple[str, str, bytes, bytes]:
        salt = secrets.token_bytes(16)
        digest = hashlib.sha256(salt + password.encode("utf-8")).digest()
        uid = "lab-" + hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]
        return uid, name, salt, digest

    def register_account(self, name: str, password: str) -> bool:
        with self.lock:
            row = self.db.execute("SELECT name, salt, digest FROM accounts WHERE name=?", (name,)).fetchone()
            if row is not None:
                return hmac.compare_digest(row[2], hashlib.sha256(row[1] + password.encode("utf-8")).digest())
            uid, _, salt, digest = self._new_account(name, password)
            self.db.execute("INSERT INTO accounts(uid,name,salt,digest) VALUES(?,?,?,?)", (uid, name, salt, digest))
            self.db.commit()
            return True

    def login_account(self, name: str, password: str) -> tuple[str, str] | None:
        with self.lock:
            row = self.db.execute("SELECT uid, salt, digest FROM accounts WHERE name=?", (name,)).fetchone()
            if row is None:
                uid, _, salt, digest = self._new_account(name, password)
                self.db.execute("INSERT INTO accounts(uid,name,salt,digest) VALUES(?,?,?,?)", (uid, name, salt, digest))
                self.db.commit()
            else:
                uid, salt, digest = row
                if not hmac.compare_digest(digest, hashlib.sha256(salt + password.encode("utf-8")).digest()):
                    return None
            token = "lab-" + secrets.token_urlsafe(32)
            self.tokens[token] = (uid, name)
            return uid, token

    def authenticate_token(self, token: str) -> dict[str, str] | None:
        with self.lock:
            value = self.tokens.get(token)
            return None if value is None else {"uid": value[0], "name": value[1]}

    def has_uid(self, uid: str) -> bool:
        with self.lock:
            return self.db.execute("SELECT 1 FROM accounts WHERE uid=?", (uid,)).fetchone() is not None

    @staticmethod
    def _add_snapshot_defaults(player: dict[str, Any]) -> bool:
        changed = False
        for group, defaults in _SNAPSHOT_DEFAULTS.items():
            state = player.get(group)
            if not isinstance(state, dict):
                continue
            for key, value in defaults.items():
                if key not in state:
                    state[key] = copy.deepcopy(value)
                    changed = True
        return changed

    @staticmethod
    def _recompute_power(player: dict[str, Any]) -> bool:
        roles = player.get("team", {}).get("roles")
        if not isinstance(roles, dict):
            return False
        changed = False
        total = 0
        for role in roles.values():
            if not role_supported(role):
                if isinstance(role, dict) and type(role.get("power")) in (int, float) and math.isfinite(role["power"]):
                    total += role["power"]
                continue
            _, growth = role_growth(role["kindId"], role["star"])
            for key, value in growth.items():
                field = f"{key}Growth"
                if role["attr"].get(field) != value:
                    role["attr"][field] = value
                    changed = True
            for item in role["equipments"].values():
                if (isinstance(item, dict) and type(item.get("kindId")) is int
                        and item["kindId"] in table("evolutionItemData")
                        and type(item.get("level")) is int and item["level"] > 0):
                    attrs = equipment_attrs(item)
                    if item.get("attrs") != attrs:
                        item["attrs"] = attrs
                        changed = True
            power = role_power(role)
            total += power
            if role.get("power") != power:
                role["power"] = power
                changed = True
        if player.get("power") != round(total, 6):
            player["power"] = round(total, 6)
            changed = True
        return changed

    @staticmethod
    def _next_bag_index(items: dict[str, Any]) -> str:
        numeric = [int(key) for key in items if isinstance(key, str) and key.isdecimal()]
        return str(max(numeric, default=0) + 1)

    @staticmethod
    def _add_drop(player: dict[str, Any], entity_id: int, count: int, extra: dict[str, Any] | None = None) -> None:
        if count <= 0:
            return
        if entity_id == 101:
            player["coin"] = int(player.get("coin", 0)) + count
            return
        if entity_id == 102:
            player["gem"] = int(player.get("gem", 0)) + count
            return
        items = player.setdefault("bag", {}).setdefault("items", {})
        for item in items.values():
            if isinstance(item, dict) and item.get("kindId") == entity_id and (extra is None or item.get("extra") == extra):
                item["count"] = int(item.get("count", 0)) + count
                return
        value: dict[str, Any] = {"kindId": entity_id, "count": count}
        if extra:
            value["extra"] = copy.deepcopy(extra)
        items[PlayerStore._next_bag_index(items)] = value

    @staticmethod
    def _drop_map(player: dict[str, Any], drops: tuple[tuple[int, int], ...]) -> dict[str, int]:
        result: dict[str, int] = {}
        for entity_id, count in drops:
            PlayerStore._add_drop(player, entity_id, count)
            key = str(entity_id)
            result[key] = result.get(key, 0) + count
        return result

    @staticmethod
    def _entity_drop(desc: str) -> tuple[tuple[int, int], ...]:
        drops: list[tuple[int, int]] = []
        for part in desc.split(","):
            item, count = part.split("x", 1)
            drops.append((int(item.split("_")[0]), int(count.split("_")[0])))
        return tuple(drops)

    @staticmethod
    def _build_role(kind_id: int, star: int = 1) -> dict[str, Any] | None:
        row = table("roleData").get(kind_id)
        if kind_id not in SUPPORTED_ROLE_IDS or row is None or type(star) is not int or star not in STAR_GROWTH:
            return None
        factor = STAR_GROWTH[star]
        init = {
            key: int(row[f"init{key.capitalize()}"]) + int(row[f"{key}Growth"] * factor)
            for key in ("hp", "atk", "def", "mdef")
        }
        init.update({"hit": int(row["hit"]), "dodge": int(row["dodge"]), "crit": int(row["crit"])})
        equipment: dict[str, Any] = {}
        equipment_attr = {key: 0 for key in ("hp", "atk", "def", "mdef", "hit", "dodge", "crit")}
        for index, item_id in enumerate(row["initEvlItemIds"], 1):
            equipment[f"evlItem_{index}"] = {"kindId": item_id, "level": 1}
            item_row = table("evolutionItemData").get(item_id)
            for field, value in (item_row or {}).get("effect", {}).items():
                if field.startswith("init"):
                    equipment_attr[field[4:].lower()] += int(value)
        attrs = {key: init[key] + equipment_attr[key] for key in init}
        return {
            "kindId": kind_id, "level": 1, "star": star, "awakeLevel": 0,
            "experience": 0, "nextLevelExp": 25, "power": 0, "mp": 0,
            "attr": attrs, "initAttr": init, "equipmentsAttr": equipment_attr,
            "equipments": equipment, "skills": {str(kind_id): {"kindId": kind_id, "level": 1}},
            "awakeSkills": {}, "awakeRateIncreaseTimes": 0,
        }

    @staticmethod
    def _update_role_equipment_attrs(role: dict[str, Any]) -> None:
        equipment_attr = {key: 0 for key in ("hp", "atk", "def", "mdef", "hit", "dodge", "crit")}
        for item in role.get("equipments", {}).values():
            if not isinstance(item, dict):
                continue
            if item.get("kindId") not in table("evolutionItemData"):
                continue
            item["attrs"] = equipment_attrs(item)
            for key, value in item["attrs"].items():
                equipment_attr[key] += value
        for key in ATTR_KEYS:
            role["attr"][key] += equipment_attr[key] - role["equipmentsAttr"][key]
        role["equipmentsAttr"] = equipment_attr
        role["power"] = role_power(role)

    @staticmethod
    def _bag_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
        delta: dict[str, Any] = {}
        for key in before:
            if key not in after:
                delta[key] = None
        for key, value in after.items():
            if before.get(key) != value:
                delta[key] = copy.deepcopy(value)
        return delta

    def _candidate(self, uid: str, name: str, player_id: int, server_id: int, old_server_id: int) -> dict[str, Any]:
        now = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=7)))
        millis = int(now.timestamp() * 1000)
        stamp = now.strftime("%Y-%m-%d %H:%M:%S")
        return {
            "id": player_id, "userName": name, "name": name, "serverId": server_id, "oldServerId": old_server_id,
            "level": 1, "experience": 0, "nextLevelExp": 25, "power": 0, "gem": 50, "coin": 0, "actionPoint": 60, "skillPoint": 10, "timesMaxMap": {"actionPoint": 60, "skillPoint": 10}, "nextRecoverTimeMap": {"actionPoint": 0, "skillPoint": 0},
            "smapStarMap": {"1": {"101": {"10101": 0, "10106": 0}}},
            "smapTimesMap": {"1": {"101": {"10101": 0, "10106": 0}}},
            "photoInfo": {"photoImgId": 1001, "shipImgId": 901}, "bag": {"items": {}},
            "team": {"roles": {"1": {
                "kindId": 100101, "level": 1, "star": 1, "awakeLevel": 0,
                "experience": 0, "nextLevelExp": 25, "power": 0, "mp": 0,
                "attr": {"hp": 1752, "atk": 127, "def": 156, "mdef": 156, "hit": 100, "dodge": 28, "crit": 40},
                "initAttr": {"hp": 1201, "atk": 47, "def": 105, "mdef": 105, "hit": 100, "dodge": 0, "crit": 0},
                "equipmentsAttr": {"hp": 551, "atk": 80, "def": 51, "mdef": 51, "hit": 0, "dodge": 28, "crit": 40},
                "equipments": {
                    "evlItem_1": {"kindId": 30101, "level": 1}, "evlItem_2": {"kindId": 30201, "level": 1},
                    "evlItem_3": {"kindId": 30301, "level": 1}, "evlItem_4": {"kindId": 30401, "level": 1},
                    "evlItem_5": {"kindId": 30501, "level": 1}, "evlItem_6": {"kindId": 30601, "level": 1},
                },
                "skills": {"100101": {"kindId": 100101, "level": 1}},
                "awakeSkills": {}, "awakeRateIncreaseTimes": 0,
            }}, "friendshipAttr": {"hp": 0, "atk": 0, "def": 0, "mdef": 0}},
            "vip": {"level": 0, "topUpGem": 0, "giftGem": 0},
            "arena": {"challengeCD": 0, "remainingChallengeTimes": 0}, "arena3v3": {"challengeCD": 0, "remainingChallengeTimes": 0},
            "point": {"freeCoinTimes": 0, "isPayGemFirst": False, "nextCoinFreeTime": 0, "nextGemFreeTime": 0},
            "activity": {"map": {}, "dial": None, "payRankAllServer": None, "powerRank": None},
            "shop": {"refreshTimesMap": {"1": 0}, "goodsMap": {"1": {
                "10001": {"entityId": 20001, "moneyId": 101, "price": 100, "count": 1, "isSaleOut": False, "requireVip": 0, "shopType": 1},
                "10002": {"entityId": 20002, "moneyId": 101, "price": 100, "count": 1, "isSaleOut": False, "requireVip": 0, "shopType": 1},
            }}, "hideRoleClassIds": [63]},
            "task": {"main": {"1": {"taskId": 0}}, "achievement": {}, "daily": {}, "receivedPointMap": {"daily": {}, "weekly": {}}, "dailyActivePoint": 0, "weeklyActivePoint": 0}, "friend": {"infoMap": {}, "list": []},
            "signInDays": 0, "signInTime": 0, "monthCardExpire": 0, "bigMonthCardExpire": 0, "yearCardExpire": 0, "weekCardExpire": 0,
            "extra": {"serverTimeStr": stamp, "serverTime": millis, "chat": {"worldList": [], "guildList": [], "allServerList": []}, "goodsList": [
                {"id": 21, "isMonthCard": 1, "isBigMonthCard": 0, "isYearCard": 0, "isWeekCard": 0, "show": "Chưa hỗ trợ", "price": 0, "gem": 0, "dailyGem": 0},
                {"id": 22, "isMonthCard": 0, "isBigMonthCard": 1, "isYearCard": 0, "isWeekCard": 0, "show": "Chưa hỗ trợ", "price": 0, "gem": 0, "dailyGem": 0},
                {"id": 23, "isMonthCard": 0, "isBigMonthCard": 0, "isYearCard": 1, "isWeekCard": 0, "show": "Chưa hỗ trợ", "price": 0, "gem": 0, "dailyGem": 0},
                {"id": 24, "isMonthCard": 0, "isBigMonthCard": 0, "isYearCard": 0, "isWeekCard": 1, "show": "Chưa hỗ trợ", "price": 0, "gem": 0, "dailyGem": 0},
            ], "mails": [], "openDays": 0,
                      "arenaRankTop1": None, "arena3v3RankTop1": None, "prestigeBattleRankTop1": None},
        }

    def create(self, uid: str, name: str, server_id: int, old_server_id: int) -> dict[str, Any]:
        with self.lock:
            try:
                self.db.execute("BEGIN IMMEDIATE")
                row = self.db.execute("SELECT id, payload FROM players WHERE uid=? AND server_id=?", (uid, server_id)).fetchone()
                if row is not None:
                    player = self._normalize_existing(int(row[0]), row[1])
                    self.db.commit()
                    return player
                cur = self.db.execute("INSERT INTO players(uid,server_id,payload) VALUES(?,?,?)", (uid, server_id, "{}"))
                candidate = self._candidate(uid, name, int(cur.lastrowid), server_id, old_server_id)
                self._add_snapshot_defaults(candidate)
                self._recompute_power(candidate)
                serialized = json.dumps(candidate, ensure_ascii=False, separators=(",", ":"))
                self.db.execute("UPDATE players SET payload=? WHERE id=?", (serialized, cur.lastrowid))
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise
            return candidate

    def _normalize_existing(self, player_id: int, payload: str) -> dict[str, Any]:
        player = json.loads(payload)
        changed = self._add_snapshot_defaults(player)
        for key, value in (("experience", 0), ("nextLevelExp", 25)):
            if key not in player:
                player[key] = value
                changed = True
        smap_fixture = {"1": {"101": {"10101": 0, "10106": 0}}}
        for key in ("smapStarMap", "smapTimesMap"):
            if not isinstance(player.get(key), dict):
                player[key] = copy.deepcopy(smap_fixture)
                changed = True
                continue
            type_map = player[key]
            if not isinstance(type_map.get("1"), dict):
                type_map["1"] = {}
                changed = True
            battle_map = type_map["1"]
            if not isinstance(battle_map.get("101"), dict):
                battle_map["101"] = {}
                changed = True
            stage_map = battle_map["101"]
            for stage in ("10101", "10106"):
                if stage not in stage_map:
                    stage_map[stage] = 0
                    changed = True
        shop = player.get("shop")
        if isinstance(shop, dict) and "hideRoleClassIds" not in shop:
            shop["hideRoleClassIds"] = [63]
            changed = True
        task = player.get("task")
        if isinstance(task, dict):
            if "daily" not in task:
                task["daily"] = {}
                changed = True
            if "receivedPointMap" not in task:
                task["receivedPointMap"] = {"daily": {}, "weekly": {}}
                changed = True
            else:
                point_map = task["receivedPointMap"]
                if isinstance(point_map, dict):
                    for key in ("daily", "weekly"):
                        if key not in point_map:
                            point_map[key] = {}
                            changed = True
            for key in ("dailyActivePoint", "weeklyActivePoint"):
                if key not in task:
                    task[key] = 0
                    changed = True
        extra = player.get("extra")
        if isinstance(extra, dict):
            chat = extra.get("chat")
            if not isinstance(chat, dict):
                extra["chat"] = {"worldList": [], "guildList": [], "allServerList": []}
                changed = True
            else:
                for key in ("worldList", "guildList", "allServerList"):
                    if key not in chat:
                        chat[key] = []
                        changed = True
        changed = self._recompute_power(player) or changed
        if not changed:
            return player
        serialized = json.dumps(player, ensure_ascii=False, separators=(",", ":"))
        self.db.execute("UPDATE players SET payload=? WHERE id=?", (serialized, player_id))
        return player

    def award_recruit(self, uid: str, player_id: int, route: str) -> dict[str, Any] | None:
        """Award one deterministic tutorial recruit, atomically and idempotently."""
        if route not in ("coin", "gem") or type(player_id) is not int or player_id <= 0:
            return None
        role_kind, role_key = ("100201", "2") if route == "coin" else ("100301", "3")
        with self.lock:
            try:
                self.db.execute("BEGIN IMMEDIATE")
                row = self.db.execute(
                    "SELECT id, payload FROM players WHERE id=? AND uid=? AND server_id=1", (player_id, uid)
                ).fetchone()
                if row is None:
                    self.db.rollback()
                    return None
                player = json.loads(row[1])
                team = player.get("team")
                roles = team.get("roles") if isinstance(team, dict) else None
                if not isinstance(roles, dict):
                    self.db.rollback()
                    return None
                existing_key = next((key for key, role in roles.items() if isinstance(role, dict)
                                     and type(role.get("kindId")) is int
                                     and role["kindId"] // 100 == int(role_kind) // 100), None)
                if existing_key is None:
                    point_state = player.get("point") if isinstance(player.get("point"), dict) else {}
                    now_ms = int(_dt.datetime.now(_dt.timezone.utc).timestamp() * 1000)
                    if route == "coin" and (
                        int(point_state.get("freeCoinTimes", 0)) >= 5
                        or int(point_state.get("nextCoinFreeTime", 0)) > now_ms
                    ):
                        self.db.rollback()
                        return None
                    if route == "gem" and (
                        bool(point_state.get("isPayGemFirst", False))
                        or int(point_state.get("nextGemFreeTime", 0)) > now_ms
                    ):
                        self.db.rollback()
                        return None
                    numeric_keys = [int(key) for key in roles if isinstance(key, str) and key.isdecimal()]
                    chosen_key = role_key if role_key not in roles else str(max(numeric_keys, default=0) + 1)
                    roles[chosen_key] = copy.deepcopy(_FIRST_RECRUIT_ROLES[role_kind])
                    point = player.setdefault("point", {})
                    if route == "coin":
                        point["freeCoinTimes"] = int(point.get("freeCoinTimes", 0)) + 1
                        point["nextCoinFreeTime"] = now_ms + 300_000
                    else:
                        point["isPayGemFirst"] = True
                        point["nextGemFreeTime"] = now_ms + 172_800_000
                    existing_key = chosen_key
                else:
                    point = player.get("point")
                    if not isinstance(point, dict):
                        point = {}
                        player["point"] = point
                    defaults = ({"freeCoinTimes": 1, "nextCoinFreeTime": 0} if route == "coin"
                                else {"isPayGemFirst": True, "nextGemFreeTime": 0})
                    for key, value in defaults.items():
                        current = point.get(key)
                        if key == "freeCoinTimes":
                            reconciled = max(current, 1) if type(current) is int else 1
                        elif key == "isPayGemFirst":
                            reconciled = True
                        else:
                            reconciled = current if key in point else value
                        if key not in point or current != reconciled:
                            point[key] = reconciled
                self._recompute_power(player)
                serialized = json.dumps(player, ensure_ascii=False, separators=(",", ":"))
                if serialized != row[1]:
                    self.db.execute("UPDATE players SET payload=? WHERE id=?", (serialized, int(row[0])))
                self.db.commit()
                point = player.get("point", {})
                response: dict[str, Any] = {
                    "code": 200,
                    "power": player["power"],
                    "team": {"roles": {str(existing_key): copy.deepcopy(roles[str(existing_key)])}},
                    "_temp": {"dropList": [{"entityId": roles[str(existing_key)]["kindId"], "count": 1,
                                            "extra": {"star": roles[str(existing_key)]["star"]}}]},
                }
                if route == "coin":
                    response["point"] = {"freeCoinTimes": point.get("freeCoinTimes", 0), "nextCoinFreeTime": point.get("nextCoinFreeTime", 0)}
                else:
                    response["point"] = {"isPayGemFirst": point.get("isPayGemFirst", False), "nextGemFreeTime": point.get("nextGemFreeTime", 0)}
                return response
            except Exception:
                self.db.rollback()
                raise

    @staticmethod
    def _stack(items: Any, key: Any, count: Any) -> dict[str, Any] | None:
        if not isinstance(items, dict) or not isinstance(key, str) or not key or type(count) is not int or count <= 0:
            return None
        item = items.get(key)
        if (not isinstance(item, dict) or type(item.get("kindId")) is not int
                or type(item.get("count")) is not int or item["count"] < count):
            return None
        return item

    @staticmethod
    def _consume(items: dict[str, Any], key: str, count: int) -> None:
        items[key]["count"] -= count
        if items[key]["count"] == 0:
            del items[key]

    def _feature_transaction(
        self, uid: str, player_id: int, server_id: int,
        change: Callable[[dict[str, Any]], dict[str, Any] | None], *, changes_team: bool = False,
    ) -> dict[str, Any] | None:
        if type(player_id) is not int or player_id <= 0 or type(server_id) is not int or server_id <= 0:
            return None
        with self.lock:
            try:
                self.db.execute("BEGIN IMMEDIATE")
                row = self.db.execute(
                    "SELECT id,payload FROM players WHERE id=? AND uid=? AND server_id=?",
                    (player_id, uid, server_id),
                ).fetchone()
                if row is None:
                    self.db.rollback()
                    return None
                if changes_team and self.db.execute(
                    "SELECT 1 FROM smap_pending WHERE player_id=? AND expires_at>?",
                    (player_id, int(time.time())),
                ).fetchone():
                    self.db.rollback()
                    return None
                before = json.loads(row[1])
                player = self._normalize_existing(int(row[0]), row[1])
                response = change(player)
                if response is None:
                    self.db.rollback()
                    return None
                self._recompute_power(player)
                for field in ("coin", "gem", "actionPoint", "power", "signInDays", "signInTime"):
                    if field in player and before.get(field) != player[field]:
                        response[field] = player[field]
                bag_delta = self._bag_delta(before.get("bag", {}).get("items", {}), player["bag"]["items"])
                if bag_delta:
                    response["bag"] = {"items": bag_delta}
                roles_delta = self._bag_delta(before["team"]["roles"], player["team"]["roles"])
                if roles_delta:
                    response["team"] = {"roles": roles_delta}
                self.db.execute(
                    "UPDATE players SET payload=? WHERE id=?",
                    (json.dumps(player, ensure_ascii=False, separators=(",", ":")), player_id),
                )
                self.db.commit()
                response["code"] = 200
                return response
            except Exception:
                self.db.rollback()
                raise

    def use_item(self, uid: str, player_id: int, bag_index: Any, item_count: Any, server_id: int = 1) -> dict[str, Any] | None:
        def change(player: dict[str, Any]) -> dict[str, Any] | None:
            items = player.get("bag", {}).get("items")
            item = self._stack(items, bag_index, item_count)
            if item is None:
                return None
            kind_id = item["kindId"]
            consumable = table("consumablesData").get(kind_id, {})
            if consumable.get("actionPoint", 0) > 0:
                if type(player.get("actionPoint")) is not int or player["actionPoint"] < 0:
                    return None
                amount = consumable["actionPoint"] * item_count
                # Consumables add purchased AP; the regeneration cap cannot erase
                # AP already granted by level-up or other items.
                player["actionPoint"] += amount
                rewards = {"99": amount}
            elif kind_id in range(321, 327):
                desc = table("entityData")[kind_id]["extra"]["dropListDesc"]
                drops = self._entity_drop(desc)
                rewards = self._drop_map(player, tuple((entity, count * item_count) for entity, count in drops))
            else:
                return None
            self._consume(items, bag_index, item_count)
            return {"_temp": {"entityCountMap": rewards}}
        return self._feature_transaction(uid, player_id, server_id, change)

    def sell_items(self, uid: str, player_id: int, bag_indices: Any, item_counts: Any, server_id: int = 1) -> dict[str, Any] | None:
        if (not isinstance(bag_indices, list) or not isinstance(item_counts, list)
                or not 1 <= len(bag_indices) <= 100 or len(bag_indices) != len(item_counts)
                or any(not isinstance(index, str) for index in bag_indices)
                or len(set(bag_indices)) != len(bag_indices)):
            return None
        def change(player: dict[str, Any]) -> dict[str, Any] | None:
            items = player.get("bag", {}).get("items")
            total = 0
            for key, count in zip(bag_indices, item_counts):
                item = self._stack(items, key, count)
                if item is None:
                    return None
                entity = table("entityData").get(item["kindId"])
                if entity is None or entity["price"] <= 0 or entity["type"] == "role":
                    return None
                total += int(entity["price"]) * count
            if type(player.get("coin")) is not int or player["coin"] < 0:
                return None
            for key, count in zip(bag_indices, item_counts):
                self._consume(items, key, count)
            player["coin"] += total
            return {"coin": player["coin"], "_temp": {"entityCountMap": {"101": total}}}
        return self._feature_transaction(uid, player_id, server_id, change)

    def use_exp_item(self, uid: str, player_id: int, team_index: Any, bag_index: Any, item_count: Any, server_id: int = 1) -> dict[str, Any] | None:
        if not isinstance(team_index, str) or not team_index:
            return None
        def change(player: dict[str, Any]) -> dict[str, Any] | None:
            role = player["team"]["roles"].get(team_index)
            items = player.get("bag", {}).get("items")
            item = self._stack(items, bag_index, item_count)
            if not role_supported(role) or item is None or not player_supported(player):
                return None
            amount = table("consumablesData").get(item["kindId"], {}).get("roleExp", 0)
            cap = min(role_max_level(player["level"]), max(ROLE_LEVEL_EXPERIENCE))
            if amount <= 0 or role["level"] > cap:
                return None
            capacity = sum(ROLE_LEVEL_EXPERIENCE[level] for level in range(role["level"], cap + 1)) - role["experience"]
            if capacity <= 0 or item_count > math.ceil(capacity / amount):
                return None
            advance_role(role, amount * item_count, player["level"])
            self._consume(items, bag_index, item_count)
            return {"_temp": {"entityCountMap": {}}}
        return self._feature_transaction(uid, player_id, server_id, change, changes_team=True)

    def evolve_equipment(self, uid: str, player_id: int, team_index: Any, equipment_type: Any, server_id: int = 1) -> dict[str, Any] | None:
        if (not isinstance(team_index, str) or not team_index or not isinstance(equipment_type, str)
                or equipment_type not in {f"evlItem_{i}" for i in range(1, 7)}):
            return None
        def change(player: dict[str, Any]) -> dict[str, Any] | None:
            role = player["team"]["roles"].get(team_index)
            if not role_supported(role):
                return None
            item = role["equipments"].get(equipment_type)
            if not isinstance(item, dict) or type(item.get("kindId")) is not int:
                return None
            current = table("evolutionItemData").get(item["kindId"])
            target_id = current.get("evolutionItemId") if current else None
            target = table("evolutionItemData").get(target_id)
            # First green tier only: later passive/buff effects remain unmapped.
            if target is None or table("entityData")[target_id]["color"] != 2:
                return None
            if type(item.get("level")) is not int or not 1 <= item["level"] <= role["level"]:
                return None
            items = player["bag"]["items"]
            before = copy.deepcopy(items)
            for entity, required in zip(target["requiredIds"], target["requiredCounts"]):
                remaining = required
                for key in list(items):
                    material = items[key]
                    if isinstance(material, dict) and material.get("kindId") == entity:
                        if self._stack(items, key, 1) is None:
                            return None
                        count = min(remaining, material["count"])
                        self._consume(items, key, count)
                        remaining -= count
                        if remaining == 0:
                            break
                if remaining:
                    return None
            # EQUIPMENTS.getEvolveCost(target color), project.js:49748.
            if type(player.get("coin")) is not int or player["coin"] < 100:
                return None
            player["coin"] -= 100
            item["kindId"] = target_id
            self._update_role_equipment_attrs(role)
            return {"coin": player["coin"], "bag": {"items": self._bag_delta(before, items)}, "_temp": {}}
        return self._feature_transaction(uid, player_id, server_id, change, changes_team=True)

    def sign_in(self, uid: str, player_id: int, now_ms: int | None = None, server_id: int = 1) -> dict[str, Any] | None:
        now_ms = int(time.time() * 1000) if now_ms is None else now_ms
        if type(now_ms) is not int or not 0 < now_ms < 253402275600000:
            return None
        def change(player: dict[str, Any]) -> dict[str, Any] | None:
            old_time, days = player.get("signInTime", 0), player.get("signInDays", 0)
            if type(old_time) is not int or type(days) is not int or old_time < 0 or days < 0:
                return None
            # Client sign-in uses isNextDay, not the separate 05:00 stage reset.
            zone = _dt.timezone(_dt.timedelta(hours=7))
            today = _dt.datetime.fromtimestamp(now_ms / 1000, zone).date()
            if old_time >= now_ms or old_time and _dt.datetime.fromtimestamp(old_time / 1000, zone).date() >= today:
                return None
            row = table("signInData").get(days + 1)
            if row is None:
                return None
            desc = row["dropListDesc"]
            multiplier = 2 if row["doubleVip"] >= 0 and player["vip"]["level"] >= row["doubleVip"] else 1
            if "_star_" in desc:
                entity_text, rest = desc.split("_star_", 1)
                star_text, count_text = rest.split("x", 1)
                entity, star = int(entity_text), int(star_text)
                if int(count_text) != 1 or multiplier != 1:
                    return None
                role = self._build_role(entity, star)
                if role is None:
                    return None
                roles = player["team"]["roles"]
                if any(isinstance(existing, dict) and type(existing.get("kindId")) is int
                       and existing["kindId"] // 100 == entity // 100 for existing in roles.values()):
                    # Duplicate-role conversion has no confirmed local contract.
                    return None
                roles[self._next_bag_index(roles)] = role
                rewards = {str(entity): 1}
            else:
                rewards = self._drop_map(player, tuple((entity, count * multiplier) for entity, count in self._entity_drop(desc)))
            player["signInDays"], player["signInTime"] = days + 1, now_ms
            return {"signInDays": days + 1, "signInTime": now_ms, "_temp": {"entityCountMap": rewards}}
        return self._feature_transaction(uid, player_id, server_id, change)

    def evolve_role(self, uid: str, player_id: int, team_index: Any, server_id: int = 1) -> dict[str, Any] | None:
        if not isinstance(team_index, str) or not team_index:
            return None
        def change(player: dict[str, Any]) -> dict[str, Any] | None:
            role = player["team"]["roles"].get(team_index)
            if not role_supported(role):
                return None
            row = table("roleData")[role["kindId"]]
            target_id = row["evolutionRoleId"]
            if target_id not in SUPPORTED_ROLE_IDS or table("entityData")[target_id]["color"] != 2:
                return None
            target = table("roleData")[target_id]
            for index, kind_id in enumerate(target["initEvlItemIds"], 1):
                item = role["equipments"].get(f"evlItem_{index}")
                if not isinstance(item, dict) or item.get("kindId") != kind_id:
                    return None
            before = copy.deepcopy(role)
            role["kindId"] = target_id
            # Green unlocks skillIds[1]; retain all existing skill levels.
            skill_id = row["skillIds"][1]
            role["skills"].setdefault(str(skill_id), {"kindId": skill_id, "level": 1})
            return {"coin": player["coin"], "_temp": {"preRole": before}}
        return self._feature_transaction(uid, player_id, server_id, change, changes_team=True)

    @staticmethod
    def _canonical_team_indices(team_indices: Any) -> tuple[str, ...] | None:
        if not isinstance(team_indices, list) or not 1 <= len(team_indices) <= 5:
            return None
        if any(not isinstance(index, str) or not index for index in team_indices):
            return None
        if len(set(team_indices)) != len(team_indices):
            return None
        return tuple(sorted(team_indices))

    def begin_smap(self, uid: str, player_id: int, smap_id: Any, team_indices: Any, server_id: int = 1) -> dict[str, Any] | None:
        """Begin one supported first-map SMAP; combat remains client-simulated."""
        canonical = self._canonical_team_indices(team_indices)
        if type(player_id) is not int or player_id <= 0 or type(smap_id) is not int or smap_id not in FIRST_MAP_RULES or canonical is None:
            return None
        rule = FIRST_MAP_RULES[smap_id]
        encoded_indices = json.dumps(canonical, separators=(",", ":"))
        now = int(time.time())
        with self.lock:
            try:
                self.db.execute("BEGIN IMMEDIATE")
                row = self.db.execute(
                    "SELECT id,payload FROM players WHERE id=? AND uid=? AND server_id=?",
                    (player_id, uid, server_id),
                ).fetchone()
                if row is None:
                    self.db.rollback()
                    return None
                player = self._normalize_existing(int(row[0]), row[1])
                pending = self.db.execute(
                    "SELECT smap_id,team_indices,expires_at FROM smap_pending WHERE player_id=?",
                    (player_id,),
                ).fetchone()
                if pending is not None and int(pending[2]) <= now:
                    self.db.execute("DELETE FROM smap_pending WHERE player_id=?", (player_id,))
                    pending = None
                if pending is not None:
                    if int(pending[0]) == smap_id and pending[1] == encoded_indices:
                        self.db.commit()
                        return {"code": 200, "actionPoint": player["actionPoint"], "_temp": {"showEntityIdsMap": {}}}
                    self.db.rollback()
                    return None

                stage_key = str(smap_id)
                stage_stars = player.get("smapStarMap", {}).get("1", {}).get("101", {})
                stage_times = player.get("smapTimesMap", {}).get("1", {}).get("101", {})
                stars = stage_stars.get(stage_key, 0)
                attempts = stage_times.get(stage_key, 0)
                action_point = player.get("actionPoint")
                roles = player.get("team", {}).get("roles")
                previous_unlocked = smap_id == 10101 or stage_stars.get(str(smap_id - 1), 0) > 0
                if (type(stars) is not int or stars < 0 or (stars > 0 and not rule.repeatable)
                        or type(attempts) is not int or not 0 <= attempts < rule.attempts
                        or type(action_point) is not int or action_point < rule.action_point
                        or not player_supported(player) or not previous_unlocked
                        or not isinstance(roles, dict)
                        or any(index not in roles or not role_supported(roles[index]) for index in canonical)):
                    self.db.rollback()
                    return None
                player["actionPoint"] = action_point - rule.action_point
                self.db.execute(
                    "INSERT INTO smap_pending(player_id,uid,server_id,smap_id,team_indices,expires_at) VALUES(?,?,?,?,?,?)",
                    (player_id, uid, server_id, smap_id, encoded_indices, now + _SMAP_PENDING_TTL_SECONDS),
                )
                serialized = json.dumps(player, ensure_ascii=False, separators=(",", ":"))
                self.db.execute("UPDATE players SET payload=? WHERE id=?", (serialized, player_id))
                self.db.commit()
                return {"code": 200, "actionPoint": player["actionPoint"], "_temp": {"showEntityIdsMap": {}}}
            except Exception:
                self.db.rollback()
                raise

    def end_smap(self, uid: str, player_id: int, star: Any, team_indices: Any, server_id: int = 1) -> dict[str, Any] | None:
        """Settle one live 10101 pending record from the APK's client-reported star."""
        canonical = self._canonical_team_indices(team_indices)
        if type(player_id) is not int or player_id <= 0 or type(star) is not int or not 0 <= star <= 3 or canonical is None:
            return None
        encoded_indices = json.dumps(canonical, separators=(",", ":"))
        now = int(time.time())
        with self.lock:
            try:
                self.db.execute("BEGIN IMMEDIATE")
                row = self.db.execute(
                    "SELECT id,payload FROM players WHERE id=? AND uid=? AND server_id=?",
                    (player_id, uid, server_id),
                ).fetchone()
                if row is None:
                    self.db.rollback()
                    return None
                pending = self.db.execute(
                    "SELECT smap_id,team_indices,expires_at,uid,server_id FROM smap_pending WHERE player_id=?",
                    (player_id,),
                ).fetchone()
                if pending is None:
                    self.db.rollback()
                    return None
                if int(pending[2]) <= now:
                    self.db.execute("DELETE FROM smap_pending WHERE player_id=?", (player_id,))
                    self.db.commit()
                    return None
                if (int(pending[0]) not in FIRST_MAP_RULES or pending[1] != encoded_indices
                        or pending[3] != uid or int(pending[4]) != server_id):
                    self.db.rollback()
                    return None

                player = json.loads(row[1])
                smap_id = int(pending[0])
                rule = FIRST_MAP_RULES[smap_id]
                stage_key = str(smap_id)
                times_type_one = player["smapTimesMap"]["1"]
                stage_times = times_type_one["101"]
                attempts = stage_times.get(stage_key, 0)
                if type(attempts) is not int or not 0 <= attempts < rule.attempts:
                    self.db.rollback()
                    return None
                stage_times[stage_key] = attempts + 1
                response: dict[str, Any] = {
                    "code": 200,
                    "actionPoint": player["actionPoint"],
                    "smapTimesMap": {"1": copy.deepcopy(times_type_one)},
                    "_temp": {"entityCountMap": {}},
                }
                if star > 0:
                    roles = player.get("team", {}).get("roles")
                    if (not isinstance(roles, dict)
                            or any(index not in roles or not role_supported(roles[index]) for index in canonical)
                            or type(player.get("coin")) is not int or not player_supported(player)):
                        self.db.rollback()
                        return None
                    player["coin"] += rule.coin
                    player_leveled = advance_player(player, rule.player_experience)
                    for index in canonical:
                        advance_role(roles[index], rule.role_experience, player["level"])
                    self._recompute_power(player)
                    star_type_one = player["smapStarMap"]["1"]
                    old_star = star_type_one["101"].get(stage_key, 0)
                    star_type_one["101"][stage_key] = max(old_star, star)
                    entity_count = self._drop_map(player, rule.drops)
                    response.update({
                        "coin": player["coin"],
                        "experience": player["experience"],
                        "actionPoint": player["actionPoint"],
                        "smapStarMap": {"1": copy.deepcopy(star_type_one)},
                        "team": {"roles": {index: copy.deepcopy(roles[index]) for index in canonical}},
                        "power": player["power"],
                        "bag": {"items": copy.deepcopy(player["bag"]["items"])},
                    })
                    response["_temp"]["entityCountMap"] = entity_count
                    if player_leveled:
                        response.update({
                            "level": player["level"],
                            "nextLevelExp": player["nextLevelExp"],
                            "timesMaxMap": copy.deepcopy(player["timesMaxMap"]),
                        })
                self.db.execute("DELETE FROM smap_pending WHERE player_id=?", (player_id,))
                serialized = json.dumps(player, ensure_ascii=False, separators=(",", ":"))
                self.db.execute("UPDATE players SET payload=? WHERE id=?", (serialized, player_id))
                self.db.commit()
                return response
            except Exception:
                self.db.rollback()
                raise

    def list_players(self, uid: str, server_id: int = 1) -> list[dict[str, int]]:
        with self.lock:
            return [{"id": int(row[0])} for row in self.db.execute("SELECT id FROM players WHERE uid=? AND server_id=? ORDER BY id", (uid, server_id))]

    def get_owned(self, uid: str, player_id: int, server_id: int = 1) -> dict[str, Any] | None:
        with self.lock:
            try:
                self.db.execute("BEGIN IMMEDIATE")
                row = self.db.execute("SELECT id, payload FROM players WHERE id=? AND uid=? AND server_id=?", (player_id, uid, server_id)).fetchone()
                if row is None:
                    self.db.rollback()
                    return None
                player = self._normalize_existing(int(row[0]), row[1])
                self.db.commit()
                return player
            except Exception:
                self.db.rollback()
                raise

    def rename(self, uid: str, player_id: int, name: str, server_id: int = 1) -> dict[str, str] | None:
        """Apply first-name selection only; paid renames remain unsupported."""
        # Local input policy, not a recovered historical name-validation rule.
        if not isinstance(name, str) or not name.strip() or len(name) > 64 or not name.isprintable():
            return None
        with self.lock:
            try:
                self.db.execute("BEGIN IMMEDIATE")
                row = self.db.execute(
                    "SELECT id, payload FROM players WHERE id=? AND uid=? AND server_id=?",
                    (player_id, uid, server_id),
                ).fetchone()
                if row is None:
                    self.db.rollback()
                    return None
                player = json.loads(row[1])
                if name == player["userName"] or player["name"] not in (player["userName"], name):
                    self.db.rollback()
                    return None
                player["name"] = name
                serialized = json.dumps(player, ensure_ascii=False, separators=(",", ":"))
                self.db.execute("UPDATE players SET payload=? WHERE id=?", (serialized, int(row[0])))
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise
            return {"name": name}
