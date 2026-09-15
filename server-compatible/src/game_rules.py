"""Finite APK-derived rules for normal map 101 stages 10101 through 10106."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from game_content import table


@dataclass(frozen=True)
class SmapRule:
    smap_id: int
    repeatable: bool
    action_point: int = 6
    role_experience: int = 20
    player_experience: int = 6
    coin: int = 1200
    attempts: int = 10
    drops: tuple[tuple[int, int], ...] = ()


FIRST_MAP_RULES = {
    # Deterministic local policy: one of each displayed material per victory.
    # APK specifyDropValues are not established item counts/probabilities.
    10101: SmapRule(10101, False, drops=((42102, 1), (42202, 1))),
    10102: SmapRule(10102, True, drops=((40102, 1), (40202, 1))),
    10103: SmapRule(10103, False, drops=((42302, 1), (42402, 1))),
    10104: SmapRule(10104, True, drops=((40302, 1), (40402, 1))),
    10105: SmapRule(10105, False, drops=((42502, 1), (42602, 1))),
    10106: SmapRule(10106, True, drops=((40502, 1), (40602, 1))),
}

# experienceData rows used by this finite first-map slice. Each value is the
# threshold attached to the entity's current level.
_EXPERIENCE_ROWS = table("experienceData")
PLAYER_LEVEL_EXPERIENCE = {row["level"]: row["playerExp"] for row in _EXPERIENCE_ROWS.values()
                           if 1 <= row["level"] <= 100 and row.get("playerExp", 0)}
ROLE_LEVEL_EXPERIENCE = {row["level"]: row["roleExp"] for row in _EXPERIENCE_ROWS.values()
                        if 1 <= row["level"] <= 100 and row.get("roleExp", 0)}
ATTR_KEYS = ("hp", "atk", "def", "mdef", "hit", "dodge", "crit")
STAR_GROWTH = {1: 1, 2: 1.5, 3: 2, 4: 2.5, 5: 3}
SUPPORTED_ROLE_IDS = frozenset(base + color for base in (100100, 100200, 100300, 100700) for color in (1, 2))

# roleData rows at 45463 and ROLE.CONSTS.STAR_GROWTH[1] == 1. Growth is
# floored before multiplying by level, exactly as roleScene.genData does.
def role_growth(kind_id: int, star: int = 1) -> tuple[dict[str, int], dict[str, int]] | None:
    """White/green starter and sign-in roles, before passive-skill unlocks."""
    if type(kind_id) is not int or kind_id not in SUPPORTED_ROLE_IDS or star not in STAR_GROWTH:
        return None
    row = table("roleData")[kind_id]
    base = {key: row[f"init{key.capitalize()}"] for key in ("hp", "atk", "def", "mdef")}
    growth = {key: math.floor(row[f"{key}Growth"] * STAR_GROWTH[star]) for key in base}
    return base, growth


def equipment_attrs(item: dict[str, Any]) -> dict[str, int]:
    effect = table("evolutionItemData")[item["kindId"]]["effect"]
    return {key: math.floor(effect.get(f"init{key.capitalize()}", 0)
                            + effect.get(f"{key}Growth", 0) * (item["level"] - 1)) for key in ATTR_KEYS}


def role_max_level(player_level: int) -> int:
    return player_level + 5 if player_level <= 10 else 20 if player_level < 20 else player_level


def role_power(role: dict[str, Any]) -> float:
    # getPower's caller was server-side. The level argument is a local policy;
    # coefficients below are recovered verbatim (project.js:49701).
    attr = role["attr"]
    return round((
        attr["hp"] / 10 + attr["atk"] + attr["def"] + attr["mdef"]
        + 2 * attr.get("hit", 0) + 2 * attr.get("dodge", 0) + 2 * attr.get("crit", 0)
        + 6000 * attr.get("unDizzinessRate", 0) + 8000 * attr.get("critRate", 0)
        + 6000 * attr.get("dmg2HpRate", 0) + 7000 * attr.get("dodgeRate", 0)
        + 3500 * attr.get("atkSpeedRate", 0) + 10 * attr.get("keepMp", 0)
        + 30 * role.get("level", 0)
    ), 6)


def advance_experience(entity: dict[str, Any], amount: int, thresholds: dict[int, int], max_level: int) -> int:
    """Apply serverConfig.addExperience arithmetic; return number of levels gained."""
    old_level = entity["level"]
    entity["experience"] += amount
    while entity["experience"] >= entity["nextLevelExp"] and entity["level"] < max_level:
        entity["experience"] -= entity["nextLevelExp"]
        entity["level"] += 1
        next_threshold = thresholds.get(entity["level"])
        if next_threshold is None:
            raise ValueError("unsupported first-map experience level")
        entity["nextLevelExp"] = next_threshold
    return entity["level"] - old_level


def role_supported(role: Any) -> bool:
    if not isinstance(role, dict) or type(role.get("kindId")) is not int or role["kindId"] not in SUPPORTED_ROLE_IDS:
        return False
    scalar_types = {
        "kindId": int, "level": int, "star": int, "awakeLevel": int,
        "experience": int, "nextLevelExp": int, "power": (int, float), "mp": (int, float),
    }
    for key, expected in scalar_types.items():
        value = role.get(key)
        if isinstance(value, bool) or not isinstance(value, expected):
            return False
    level = role["level"]
    if role["star"] not in STAR_GROWTH or role["awakeLevel"] != 0 or level not in ROLE_LEVEL_EXPERIENCE or role["nextLevelExp"] != ROLE_LEVEL_EXPERIENCE[level]:
        return False
    if not 0 <= role["experience"] <= role["nextLevelExp"]:
        return False
    required_maps = ("attr", "initAttr", "equipmentsAttr", "equipments", "skills", "awakeSkills")
    if any(not isinstance(role.get(key), dict) for key in required_maps):
        return False
    if any(type(role[field].get(key)) not in (int, float) or not math.isfinite(role[field][key])
           for field in ("attr", "initAttr", "equipmentsAttr") for key in ATTR_KEYS):
        return False
    return all(isinstance(skill, dict) and type(skill.get("level")) is int and skill["level"] > 0
               for skill in role["skills"].values())


def advance_role(role: dict[str, Any], amount: int, player_level: int) -> None:
    old_init = dict(role["initAttr"])
    cap = min(role_max_level(player_level), max(ROLE_LEVEL_EXPERIENCE))
    leveled = advance_experience(role, amount, ROLE_LEVEL_EXPERIENCE, cap)
    if role["level"] == cap:
        role["experience"] = min(role["experience"], role["nextLevelExp"])
    if not leveled:
        return
    growth_row = role_growth(role["kindId"], role["star"])
    if growth_row is None:
        raise ValueError("unsupported first-map role")
    base, growth = growth_row
    new_init = {
        key: math.floor(base[key] + growth[key] * role["level"])
        for key in ("hp", "atk", "def", "mdef")
    }
    new_init.update({"hit": 100, "dodge": 0, "crit": 0})
    for key in ("hp", "atk", "def", "mdef", "hit", "dodge", "crit"):
        role["attr"][key] += new_init[key] - old_init[key]
    role["initAttr"] = new_init


def player_supported(player: dict[str, Any]) -> bool:
    level = player.get("level")
    experience = player.get("experience")
    return (type(level) is int and level in PLAYER_LEVEL_EXPERIENCE
            and type(experience) is int and 0 <= experience <= PLAYER_LEVEL_EXPERIENCE[level]
            and (experience < PLAYER_LEVEL_EXPERIENCE[level] or level == 100)
            and player.get("nextLevelExp") == PLAYER_LEVEL_EXPERIENCE[level])


def advance_player(player: dict[str, Any], amount: int) -> bool:
    old_level = player["level"]
    levels_gained = advance_experience(player, amount, PLAYER_LEVEL_EXPERIENCE, 100)
    if player["level"] == 100:
        player["experience"] = min(player["experience"], player["nextLevelExp"])
    if levels_gained:
        # PLAYER.FUNS.getUpgradeIncreaseActionPoint, project.js:49602.
        for level in range(old_level + 1, old_level + levels_gained + 1):
            player["actionPoint"] += (20 if level <= 7 else 30 if level <= 11 else 40 if level <= 20
                                      else 60 if level <= 30 else 80 if level <= 40 else 100 if level <= 50 else 120)
        # PLAYER.FUNS.getActionPointMax(level) is CREATE_PLAYER max (60)
        # plus the current level. Preserve skillPoint while syncing the cap
        # consumed by the recovered client's AP recovery display.
        player["timesMaxMap"]["actionPoint"] = 60 + player["level"]
    return levels_gained > 0
