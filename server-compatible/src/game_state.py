"""Durable local account and player state for the recovered game-entry flow."""

from __future__ import annotations

import base64
import copy
import datetime as _dt
import gzip
import hashlib
import hmac
import json
import secrets
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any


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

_FIRST_SMAP_ID = 10101
_FIRST_SMAP_AP = 6
_FIRST_SMAP_ATTEMPTS = 10
_FIRST_SMAP_COIN = 1200
_FIRST_SMAP_PLAYER_XP = 6
_FIRST_SMAP_ROLE_XP = 20
# Local compatibility policy: enough for a lab playthrough, finite so an
# abandoned client-local simulation cannot block the player permanently.
_SMAP_PENDING_TTL_SECONDS = 30 * 60


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
                serialized = json.dumps(candidate, ensure_ascii=False, separators=(",", ":"))
                self.db.execute("UPDATE players SET payload=? WHERE id=?", (serialized, cur.lastrowid))
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise
            return candidate

    def _normalize_existing(self, player_id: int, payload: str) -> dict[str, Any]:
        player = json.loads(payload)
        changed = False
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
        if not changed:
            return player
        serialized = json.dumps(player, ensure_ascii=False, separators=(",", ":"))
        self.db.execute("UPDATE players SET payload=? WHERE id=?", (serialized, player_id))
        return player

    def award_recruit(self, uid: str, player_id: int, route: str) -> dict[str, Any] | None:
        """Award one deterministic tutorial recruit, atomically and idempotently."""
        if route not in ("coin", "gem") or not isinstance(player_id, int) or player_id <= 0:
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
                existing_key = next((key for key, role in roles.items() if isinstance(role, dict) and str(role.get("kindId")) == role_kind), None)
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
                    serialized = json.dumps(player, ensure_ascii=False, separators=(",", ":"))
                    self.db.execute("UPDATE players SET payload=? WHERE id=?", (serialized, int(row[0])))
                    self.db.commit()
                    existing_key = chosen_key
                else:
                    point = player.get("point")
                    if not isinstance(point, dict):
                        point = {}
                        player["point"] = point
                    marker_changed = False
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
                            marker_changed = True
                    if marker_changed:
                        serialized = json.dumps(player, ensure_ascii=False, separators=(",", ":"))
                        self.db.execute("UPDATE players SET payload=? WHERE id=?", (serialized, int(row[0])))
                        self.db.commit()
                    else:
                        self.db.rollback()
                point = player.get("point", {})
                response: dict[str, Any] = {
                    "code": 200,
                    "team": {"roles": {str(existing_key): copy.deepcopy(roles[str(existing_key)])}},
                    "_temp": {"dropList": [{"entityId": int(role_kind), "count": 1, "extra": {"star": 1}}]},
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
    def _canonical_team_indices(team_indices: Any) -> tuple[str, ...] | None:
        if not isinstance(team_indices, list) or not 1 <= len(team_indices) <= 5:
            return None
        if any(not isinstance(index, str) or not index for index in team_indices):
            return None
        if len(set(team_indices)) != len(team_indices):
            return None
        return tuple(sorted(team_indices))

    @staticmethod
    def _first_battle_role_supported(role: Any) -> bool:
        if not isinstance(role, dict):
            return False
        scalar_types = {
            "kindId": int, "level": int, "star": int, "awakeLevel": int,
            "experience": int, "nextLevelExp": int, "power": (int, float), "mp": (int, float),
        }
        for key, expected in scalar_types.items():
            value = role.get(key)
            if isinstance(value, bool) or not isinstance(value, expected):
                return False
        if role["level"] != 1 or role["experience"] != 0 or role["nextLevelExp"] != 25:
            return False
        attr = role.get("attr")
        if not isinstance(attr, dict):
            return False
        if any(isinstance(attr.get(key), bool) or not isinstance(attr.get(key), (int, float))
               for key in ("hp", "atk", "def", "mdef", "hit", "dodge", "crit")):
            return False
        return isinstance(role.get("skills"), dict) and isinstance(role.get("awakeSkills"), dict)

    def begin_smap(self, uid: str, player_id: int, smap_id: Any, team_indices: Any, server_id: int = 1) -> dict[str, Any] | None:
        """Begin only APK SMAP 10101; combat itself remains client-simulated."""
        canonical = self._canonical_team_indices(team_indices)
        if type(player_id) is not int or player_id <= 0 or type(smap_id) is not int or smap_id != _FIRST_SMAP_ID or canonical is None:
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

                stars = player.get("smapStarMap", {}).get("1", {}).get("101", {}).get("10101")
                attempts = player.get("smapTimesMap", {}).get("1", {}).get("101", {}).get("10101")
                action_point = player.get("actionPoint")
                roles = player.get("team", {}).get("roles")
                player_xp = player.get("experience")
                if (type(stars) is not int or stars != 0 or type(attempts) is not int
                        or not 0 <= attempts < _FIRST_SMAP_ATTEMPTS
                        or type(action_point) is not int or action_point < _FIRST_SMAP_AP
                        or type(player.get("level")) is not int or player["level"] != 1
                        or type(player_xp) is not int or not 0 <= player_xp <= 18
                        or player.get("nextLevelExp") != 25 or not isinstance(roles, dict)
                        or any(index not in roles or not self._first_battle_role_supported(roles[index]) for index in canonical)):
                    self.db.rollback()
                    return None
                player["actionPoint"] = action_point - _FIRST_SMAP_AP
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
                if (int(pending[0]) != _FIRST_SMAP_ID or pending[1] != encoded_indices
                        or pending[3] != uid or int(pending[4]) != server_id):
                    self.db.rollback()
                    return None

                player = json.loads(row[1])
                times_type_one = player["smapTimesMap"]["1"]
                stage_times = times_type_one["101"]
                attempts = stage_times.get("10101")
                if type(attempts) is not int or not 0 <= attempts < _FIRST_SMAP_ATTEMPTS:
                    self.db.rollback()
                    return None
                stage_times["10101"] = attempts + 1
                response: dict[str, Any] = {
                    "code": 200,
                    "actionPoint": player["actionPoint"],
                    "smapTimesMap": {"1": copy.deepcopy(times_type_one)},
                    "_temp": {"entityCountMap": {}},
                }
                if star > 0:
                    roles = player.get("team", {}).get("roles")
                    if (not isinstance(roles, dict)
                            or any(index not in roles or not self._first_battle_role_supported(roles[index]) for index in canonical)
                            or type(player.get("coin")) is not int or type(player.get("experience")) is not int
                            or player.get("nextLevelExp") != 25
                            or player["smapStarMap"]["1"]["101"].get("10101") != 0):
                        self.db.rollback()
                        return None
                    player["coin"] += _FIRST_SMAP_COIN
                    player["experience"] += _FIRST_SMAP_PLAYER_XP
                    for index in canonical:
                        roles[index]["experience"] += _FIRST_SMAP_ROLE_XP
                    star_type_one = player["smapStarMap"]["1"]
                    star_type_one["101"]["10101"] = star
                    response.update({
                        "coin": player["coin"],
                        "experience": player["experience"],
                        "smapStarMap": {"1": copy.deepcopy(star_type_one)},
                        "team": {"roles": {index: copy.deepcopy(roles[index]) for index in canonical}},
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
