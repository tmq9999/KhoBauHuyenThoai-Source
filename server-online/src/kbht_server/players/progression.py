"""Recovered serverConfig49464,49698 XP semantics; no compatibility imports."""
def role_cap(player_level):
    return player_level + 5 if player_level <= 10 else 20 if player_level < 20 else player_level


def upgrade_action_point(level):
    """Source49602: getUpgradeIncreaseActionPoint(destination level)."""
    for ceiling, amount in ((7,20),(11,30),(20,40),(30,60),(40,80),(50,100)):
        if level <= ceiling:
            return amount
    return 120


def advance(level, experience, amount, cap, table, field):
    if any(type(v) is not int or v < 0 for v in (level,experience,amount,cap)) or not 1 <= level <= cap <= 100:
        raise ValueError('unsupported progression state')
    experience += amount
    while level < cap and experience >= table[str(level)][field]:
        cost = table[str(level)][field]
        if type(cost) is not int or cost <= 0:
            raise ValueError('invalid progression table')
        experience -= cost
        level += 1
    if experience > 9007199254740991:
        raise ValueError('experience overflow')
    return level, experience
