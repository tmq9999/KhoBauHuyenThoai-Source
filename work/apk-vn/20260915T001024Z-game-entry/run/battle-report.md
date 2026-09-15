# First playable SMAP 10101 — implementation report

## Scope and evidence

Implemented the finite APK-native first battle slice described by
`battle-brief.md` and `first-battle-contract.md`. The recovered client sends
only `smapId`, `teamIndexs`, `star`, and `teamIndexs`; it locally simulates the
combat from `project.js` and reports the resulting star. The local service does
not fabricate combat, accept a seed/transcript, or claim historical anti-cheat
or server-verified battle parity.

Changed scope only:

- `server-compatible/src/game_state.py`
- `server-compatible/src/game_server.py`
- `server-compatible/tests/protocol/test_game_battle.py`

## RED

Before production changes:

```text
python -m pytest -q -p no:cacheprovider server-compatible/tests/protocol/test_game_battle.py --basetemp .pytest-battle-red
20 failed, 1 passed
```

The expected failures were missing `PlayerStore.begin_smap`/
`PlayerStore.end_smap` and the missing WebSocket route implementation. The
one passing test was the fixed-code rejection-only route case.

## GREEN and behavior

Focused battle suite after implementation:

```text
python -m pytest -q -p no:cacheprovider server-compatible/tests/protocol/test_game_battle.py --basetemp .pytest-battle-green
21 passed
```

The implementation now:

- supports only integer stage `10101`; validates one-to-five distinct owned
  string role indices, starter-compatible level/XP state, AP >= 6, and the
  source attempt cap of 10;
- uses SQLite `BEGIN IMMEDIATE` for AP decrement and pending creation as one
  commit; duplicate identical begin is idempotent and does not debit AP;
- persists pending state in `smap_pending` across store reopen, bound to uid,
  player, stage, and canonical index set;
- expires abandoned pending records after the documented local 30-minute lab
  TTL, with no reward/attempt mutation and no permanent player dead-end;
- settles star 0 as an actual client-loss response, clears pending, increments
  the completed-attempt counter once, and awards no coin/XP/stars;
- settles stars 1..3 once with source row values: coin +1200, player XP +6,
  selected role XP +20, best star, and one attempt; returns complete selected
  role records and complete type-1 map subtrees;
- rejects duplicate/missing/mismatched/expired/cross-owner requests, invalid
  stars (including booleans), unsupported stages, malformed selections, low AP,
  exhausted attempts, completed nonrepeatable 10101, and unsupported role state;
- exposes exact `logic.smapHandler.beginSmap` and `endSmap` connector routes with
  the fixed existing Vietnamese error response on rejection; payloads are not
  logged.

## Regression verification

```text
python -m pytest -q -p no:cacheprovider server-compatible/tests/protocol/test_game_state.py server-compatible/tests/protocol/test_game_server.py server-compatible/tests/protocol/test_game_battle.py --basetemp .pytest-battle-focused
64 passed

python -m pytest -q -p no:cacheprovider server-compatible/tests/protocol --basetemp .pytest-battle-final
102 passed, 1 skipped

python -m compileall -q server-compatible/src server-compatible/tests/protocol/test_game_battle.py
git diff --check
```

The battle tests use real SQLite and real loopback WebSocket connections; no
behavioral mocks or network dependencies are used. Rollback tests use real
SQLite abort triggers and verify pending/AP/reward atomicity.

## Limits

Later stages remain unsupported. This is a finite compatibility policy for the
recovered APK flow, not a recovered historical backend implementation. The APK
provides no proof in `endSmap`, so a malicious client could still report a win;
pending binding and one-time settlement only prevent replay/cross-owner reward
duplication.
