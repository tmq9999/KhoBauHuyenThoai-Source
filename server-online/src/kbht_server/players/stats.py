"""Pure source projections: project.js46420,19624 and49702. No policy inference."""
from decimal import Decimal
from math import floor

ATTRS = ('hp', 'atk', 'def', 'mdef', 'hit', 'dodge', 'crit')


def initial_attributes(role, level, star):
    # Only the source-backed first-role star is enabled in this slice.
    if star != 1:
        raise ValueError('native star progression not implemented')
    growth = {key+'Growth': floor(role[key+'Growth']) for key in ATTRS[:4]}
    values = {key: floor(role['init'+key.capitalize()] + growth[key+'Growth']*level)
              for key in ATTRS[:4]}
    values.update({key: floor(role[key]) for key in ATTRS[4:]})
    return values, growth


def equipment_attributes(effect, level):
    return {key: floor(effect.get('init'+key.capitalize(), 0) +
                       level*effect.get(key+'Growth', 0)) for key in ATTRS}


def power_milli(attr, second_argument):
    weights = {'hp': 100, 'atk': 1000, 'def': 1000, 'mdef': 1000,
               'hit': 2000, 'dodge': 2000, 'crit': 2000, 'unDizzinessRate': 6000000,
               'critRate': 8000000, 'dmg2HpRate': 6000000, 'dodgeRate': 7000000,
               'atkSpeedRate': 3500000, 'keepMp': 10000}
    result = sum(Decimal(str(attr.get(key, 0)))*weight for key, weight in weights.items())
    result += Decimal(str(second_argument))*30000
    return floor(result)
