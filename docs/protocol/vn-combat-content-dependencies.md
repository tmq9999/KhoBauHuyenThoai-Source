# Combat/item dependency evidence — 2026-09-16

Pinned `project.js` SHA256:
`9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818`.
This is a static reference audit and immutable archive, not recovered historical
server rules, playable combat or publication approval.

## Preserved inputs

| Table | Literal rows | Notes |
| --- | ---: | --- |
| mobData | 16,245 | ID0 ship sentinel retained; no duplicate IDs |
| fightSkillData | 474 | Sparse trailing cells; ID1105010 occurs twice |
| buffData | 745 | Sparse trailing cells, !0/!1 boolean literals; ID10006 twice |
| entityData | 1,812 | Sparse extra column retained as absent, not null |
| evolutionItemData | 120 | Recipe IDs/counts and next equipment references |
| consumablesData | 7 | Raw EXP/AP values, not item-use handlers |
| dropData | 379 | Archive only; weights/reference-group semantics not validated |

Archive stores column headers plus ordered cell arrays. Duplicate rows, missing
trailing fields, unused skill levels and unknown fields are retained. The strict
`read_table` still rejects duplicate/nonpositive IDs. `read_table_archive` is
explicitly an evidence interface, not a last-wins dictionary of game rules.
Only literal normalization occurs; JS code/functions/operators are not evaluated.

## Consumer-backed edges

- `battle.mob` lines9841-9848 pairs each `skillIds[n]` with `skillLevels[n]`,
  prepending `initSkillId` at level0. Extra level cells are retained; missing
  consumed levels block the audit.
- `battle.fightskill.create` lines8800-8808 loads every skill `buffIds` entry.
- Dynamic buffs at7392/7406 reference `extra.skillId`; chained skills at7286
  consume `extra.skillIds`; revive at7327 consumes `extra.buffIds`. Skill
  allow/deny lists are also checked as references.
- Summon at9046-9067 interprets type4 skill `atkPer` as mob ID(s), not a damage
  multiplier. Audit traverses summoned mob dependencies with a visited set.
- `dataApi.findEntityById`18516 joins entity metadata to its subtype. Equipment
  UI19730-19733 consumes `evolutionItemId`, `requiredIds`, `requiredCounts`.
- Map display/drop entity ID0 means no entity slot; it is not a grant. All36
  nonzero entities directly displayed in normal stages are `fragment` records.

The audit starts with normal map waves/displayed entities, traverses mob/skill/
buff dependencies, and separately checks all equipment recipe and consumable
entity references. It does not claim all global references or combat semantics
are verified. A cycle-safe traversal is not a proof that cycles are valid rules.

## Concrete blockers

`fightSkillData` rows466 and467 (1-based data row, header excluded) both use
ID1105010 with different projectile definitions: distance300 vs600, attackType2
vs1 and different coefficients/offsets. Buff210501 references this ID, so it is
reachable from normal maps. Neither definition is silently selected.

`buffData` rows6 and7 both use ID10006: dizziness timeout9 vs silence timeout3.
The original table loader (`project.js:18452-18454`) overwrites earlier keys,
which explains client behavior, but does not establish the intended server rule.
Both source rows are preserved for a versioned conflict-resolution decision.

Current report contains two `DUPLICATE_ID` issues and one
`AMBIGUOUS_REFERENCE` to skill1105010. It returns `reference_status=BLOCKED` and
`publishable=false`. There are19,355 reported edges and14,063 consumed mob-skill
bindings; those counts do not mean battle behavior is implemented.

## Next gate

Resolve duplicate semantics through native/comparator evidence and record a
versioned explicit policy before creating unambiguous gameplay definitions.
Continue validating numeric/effect behavior, drop groups/reward meaning,
recipe cycles and material acquisition. Authoritative battle replay, native
protocol integration and APK verification remain required. No change to pinned
source, existing map draft identities, server activation or player data.
