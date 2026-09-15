# Server feature slice - 2026-09-15

## Implemented

- Added a pinned-source literal reader for recovered APK data tables. It
  validates the recovered `project.js` SHA-256 and never executes JavaScript.
- Repaired zero `power` values using the APK `getPower` coefficients and persisted
  role/player power, growth fields, equipment attributes and post-battle stats.
- Extended SMAP 10101-10106 settlement with SQLite-persisted material drops,
  AP/coin/player-EXP/role-EXP arithmetic, unlock checks and repeat/attempt rules.
- Implemented the client-observed local routes for sign-in, bag use/sell, role
  EXP items, first green equipment evolution and first green role evolution.
- Added transaction, ownership, malformed-input, retry, reconnect and
  concurrent-claim coverage.

## Verification

```text
python -m pytest -q server-compatible/tests/protocol -p no:cacheprovider --basetemp .pytest-tmp/protocol-final2 --tb=short
139 passed, 1 skipped

python -m pytest -q tests server-compatible/tests/protocol -p no:cacheprovider --basetemp .pytest-tmp/tracked-final2 --tb=short
215 passed, 3 skipped
```

The new routes were also exercised through real loopback WebSocket frames,
including login, player selection, mutation, failed re-entry and reconnect.
No APK was installed or launched, and no provider/payment endpoint was
contacted.

## Boundary

Drop counts in the six-stage compatibility slice are an explicit deterministic
local policy because the APK's `specifyDropValues` rows do not establish the
server settlement contract. Sign-in rows and data-table values are read from
the recovered client. Activity, shop, task, mail, multiplayer, later-tier
evolution and production persistence remain unsupported until their client
consumers and response/reward contracts are recovered.

The supported roles are Luffy, Zoro, Nami and the day-two Robin reward,
white/green tiers and stars 1-5 without awakening. Other roles are preserved,
not rewritten. Role power uses level for the formula's second argument and
player power sums owned roles; these are local policies because the historical
callers are absent. AP items add their full table value without reducing
existing overflow AP. The pinned table reader requires the recovered source
file alongside this repository's server.

Material 49902 is required for equipment evolution, but a complete gameplay
source for it has not been implemented. Evolution integration tests seed a
separate test database with the APK's material box (321); they do not prove
that an existing player can acquire every required item. Previously missed
battle drops are not retroactively granted: no reward ledger establishes
what was owed. Sign-in duplicate-role conversion also remains unsupported.

The running game server and its SQLite database were not restarted or edited.
Reload this code with the existing state path and re-login to repair supported
legacy role payloads. A native APK smoke test is still needed. Independent
review agents could not start because their provider credentials were absent;
verification here is local tests and direct source inspection, not an
independent review verdict.

## Static consumer references

- `client-recovered/src/project.js:49701`: power coefficients.
- `client-recovered/src/project.js:46499`: role growth and base-stat display.
- `client-recovered/src/project.js:5853`: bag count lookup; `5841` handles null
  tombstones. `40113` merges player updates and emits bag/team changes.
- `client-recovered/src/project.js:53513`: six-stage material IDs, AP and EXP.
- `client-recovered/src/project.js:39934`: sign-in route; `52774` reward rows.
- `client-recovered/src/project.js:39959`: item route; `5378` sells stacks.
- `client-recovered/src/project.js:55429`: evolution route; `46361` reads
  preRole; `55881` requires all six next-tier equipment items.
- `client-recovered/src/project.js:55490`: role EXP-item route.
