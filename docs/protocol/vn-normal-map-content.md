# Normal-map content provenance

Source: immutable `client-recovered/src/project.js`, SHA-256
`9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818`.
Evidence class: APK-static. This document describes content relationships, not
historical server code or native online-server acceptance.

## Classification and order

- `bmapData` (`project.js:13067`) provides chapter `kindId`, `rankId`, `type`,
  `levelLimit` and other raw fields. Normal chapters have `type = 1`, matching
  `MAP.CONSTS.TYPE.NORMAL` at `project.js:49835`.
- `smapData` (`project.js:53513`) provides stage `bmapId`, `rankId`, costs,
  limits and mob-wave IDs. `dataApi._init` joins `smap.bmapId` to the chapter
  (`project.js:18547`) and groups/sorts its stages by `rankId`
  (`project.js:18557`). Numeric ranges in a stage ID are not the classifier.
- `bmapScene.genData` filters chapters by type and sorts by chapter `rankId`
  (`project.js:13160`). The last stage advances its UI cursor to the next
  chapter's first stage (`project.js:13171`). This supports ordered adjacency,
  not a claim that adjacency alone is sufficient to unlock a battle.
- The first chapter has stages 10101 through 10112. Therefore content order
  includes 10106 -> 10107 and 10112 -> 10201; it does not stop at 10106.

## Literal stage 10107

Static inventory: 69 chapter rows and 1,623 stage rows; the chapter-type join
selects 27 normal chapters, 376 stages and 3,722 ordered mob-wave memberships.
Chapter 101 has 12 stages; chapters 102 through 127 each have 14. These are
source counts, not a count of playable or tested online stages.
Normal chapter ranks and each chapter's stage ranks are contiguous from 1 in
this source. Draft validation rejects gaps so missing intermediate content does
not silently become a new predecessor edge.

| Field | APK value |
| --- | --- |
| chapter / rank | 101 / 7 |
| actionPoint / roleExp / coin | 6 / 20 / 1200 |
| times / levelLimit | 10 / 0 |
| mobZone1 | 1010711, 1010712, 1010713 |
| mobZone2 | 1010721, 1010722, 1010723, 1010724, 1010725 |
| specifyDropEntityIds | 42102, 42202, 0 |
| specifyDropValues | 125, 125, 125 |

`specifyDropValues` is preserved raw. In particular, 125 is **not** interpreted
as a grant of 125 items. Drop semantics and combat validation remain separate
publication gates. Mob identifiers here are references, not validated mob/skill
definitions or a functioning battle simulation.

## Sparse rows and exclusions

Chapter rows 401, 501, 502 and 503 have only three cells against seven headers.
The client maps absent array cells to JavaScript `undefined`
(`project.js:18458`); missing type must not become type 1 or fabricated null.
An explicit sparse-table parser mode can preserve absent fields as absent keys;
the normal-map validator still requires all gameplay fields on normal rows.

Stages with `bmapId = 0` include tutorial/test data and are retained as raw
source, not normal-map definitions. Known non-normal chapters likewise remain
raw. A nonzero chapter reference without a matching source row is an error.

## Remaining release gates

The subsequent [dependency audit](vn-combat-content-dependencies.md) now archives
the seven combat/item tables and checks bounded transitive references. It found
duplicate skill/buff definitions and leaves publication blocked.

Unambiguous mob/skill/item definitions, drop interpretation, reward acquisition
paths, authoritative battle/action replay, actual unlock/attempt rules and APK
wire/native smoke are still required. Preparing a PostgreSQL draft must not
publish content, open a game server or grant a player anything.

The ordered dependency archive now preserves the observed `mobData.kindId = 0`
sentinel explicitly; the strict positive-ID parser still rejects it. Static inspection
found 16,245 mob rows and no duplicate IDs. The first mob in stage 10107,
1010711, references `initSkillId = 110900`, `skillIds = [110901]`, and
`skillLevels = [2, 2, 2, 2]`. The mob constructor loops over `skillIds.length`
and reads `skillLevels[n]` (`project.js:9841-9844`), then prepends the initial
skill with level 0 (`project.js:9845-9848`). Thus this mob uses skill 110901 at
level 2 and initial skill 110900 at level 0; the remaining level cells are not
additional skills. Preserve those raw cells for provenance rather than silently
discarding them. A future normalized importer must reject missing consumed
levels while retaining unconsumed cells. Mob/skill reference validation is a
concrete remaining task, not permission to skip those checks.

Both referenced skills exist in `fightSkillData`. Skill 110901 references buffs
210901 and 210902; its raw `atkPer = 0.6`, `initVal = 27`, `valGrowth = 19`,
`coolTime = 10` and `range = 200` are evidence to retain for a later combat
fixture, not a standalone damage formula. This table also has short trailing
rows, so the sparse-source handling must be explicit when it is imported.
