"""APK chapter relationships and normal-stage projections, not battle rules."""
import math
from typing import Any


def _integer(value: Any, field: str, minimum: int = 0) -> int:
    if (type(value) not in (int, float) or not math.isfinite(value)
            or value != int(value) or not minimum <= value <= 2**53 - 1):
        raise ValueError(f"invalid {field}")
    return int(value)


def normal_map_graph(bmap: dict[int, dict], smap: dict[int, dict]) -> dict[int, dict]:
    """Project stage order using bmap.type and both rankId fields.

    Predecessors describe content order only. Mob/item/skill reference integrity,
    reward semantics and actual progression eligibility remain publication gates.
    """
    normal = {}
    for chapter_id, chapter in bmap.items():
        _integer(chapter_id, "chapter identity", 1)
        if _integer(chapter.get("kindId"), "chapter kindId", 1) != chapter_id:
            raise ValueError("chapter kindId mismatch")
        chapter_type = chapter.get("type")
        if chapter_type is None:
            continue  # sparse non-classified rows remain in the raw archive
        _integer(chapter_type, "chapter type", 1)
        if chapter_type == 1:
            normal[chapter_id] = (
                _integer(chapter.get("rankId"), "chapter rank", 1),
                _integer(chapter.get("levelLimit"), "chapter levelLimit"),
            )
    if not normal:
        raise ValueError("no normal chapters")
    if len({rank for rank, _ in normal.values()}) != len(normal):
        raise ValueError("duplicate chapter rank")
    if sorted(rank for rank, _ in normal.values()) != list(range(1, len(normal) + 1)):
        raise ValueError("chapter rank gap")

    grouped = {chapter_id: [] for chapter_id in normal}
    for stage_id, stage in smap.items():
        _integer(stage_id, "stage identity", 1)
        if _integer(stage.get("kindId"), "stage kindId", 1) != stage_id:
            raise ValueError("stage kindId mismatch")
        chapter_id = _integer(stage.get("bmapId"), "bmapId")
        if chapter_id and chapter_id not in bmap:
            raise ValueError("dangling chapter reference")
        if chapter_id in normal:
            grouped[chapter_id].append((stage_id, stage))

    result = {}
    predecessor = None
    for chapter_id in sorted(normal, key=lambda key: normal[key][0]):
        chapter_rank, chapter_level = normal[chapter_id]
        stages = grouped[chapter_id]
        if not stages:
            raise ValueError("empty normal chapter")
        ranks = [_integer(row.get("rankId"), "stage rank", 1) for _, row in stages]
        if len(set(ranks)) != len(ranks):
            raise ValueError("duplicate stage rank")
        if sorted(ranks) != list(range(1, len(ranks) + 1)):
            raise ValueError("stage rank gap")
        for stage_id, row in sorted(stages, key=lambda pair: pair[1]["rankId"]):
            count = _integer(row.get("mobZoneCount"), "mobZoneCount", 1)
            if count > 2:
                raise ValueError("unsupported mobZoneCount")
            waves = []
            for zone in range(1, count + 1):
                mobs = row.get(f"mobZone{zone}")
                if not isinstance(mobs, list) or not mobs:
                    raise ValueError("invalid mob wave")
                waves.append([_integer(mob, "mob identity", 1) for mob in mobs])
            result[stage_id] = {
                "chapter_id": chapter_id, "chapter_rank": chapter_rank,
                "rank": int(row["rankId"]), "predecessor_id": predecessor,
                "chapter_level_limit": chapter_level,
                "action_point": _integer(row.get("actionPoint"), "actionPoint"),
                "level_limit": _integer(row.get("levelLimit"), "levelLimit"),
                "times": _integer(row.get("times"), "times", 1),
                "role_exp": _integer(row.get("roleExp"), "roleExp"),
                "coin": _integer(row.get("coin"), "coin"), "waves": waves,
            }
            predecessor = stage_id
    return result
