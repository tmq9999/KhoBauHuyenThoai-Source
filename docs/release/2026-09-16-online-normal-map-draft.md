# Online normal-map draft — service evidence

Status: SERVICE_TESTED content slice; M1.2/M6 and native acceptance remain open.
Changes are uncommitted on `feat/native-game-entry`; base `ab6f31b`.

## Delivered

- Explicit sparse chapter parsing, strict numeric/reference/rank validation.
- Chapter-based graph: 27 normal chapters, 376 maps, 3,722 wave references.
- Migration `0009_normal_maps`, layered after existing `0008_sessions`.
- Atomic source backfill and replay-checked draft materialization.
- Rollback, concurrent preparation, tamper detection and published-row guards.
- Provenance in `docs/protocol/vn-normal-map-content.md`; README/CHANGELOG and
  active plan/runbook/progress log updated.

## Verification

Using `server-online/.venv/Scripts/python.exe -I -m pytest` with the password
file environment set, no secret printed, tests only in `kbht_test`:

| Check | Result |
| --- | --- |
| Full `server-online/tests` | 243 passed in 103.72s |
| Full `tests server-compatible/tests/protocol` | 303 passed, 4 skipped in 109.76s |
| Final content tooling after review correction | 39 passed in 0.60s |
| Final PostgreSQL content/map tests after review correction | 19 passed in 15.38s |
| Node power formatter | 1 passed |
| compileall / pip check / diff check | passed |
| Static route inventory | 230 routes / 231 sites verified |

Full-suite results preceded the final rank-gap guard. The two final covering
runs include that guard. Four skips are unavailable Windows symlink privileges;
no PostgreSQL tests were skipped. Independent scoped review found the rank-gap
omission; both added tests failed before the fix and passed afterward. Reviewer
re-check: ADDRESSED, spec compliant and task quality approved.

## Preserved boundaries

APK hash `d61d4ae1994ec5bcafdcfaf2406cc88ed9611cbb65da853027799d50d6687eb4`
and project.js hash
`9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818` rechecked.
No APK build/install/launch, provider traffic, production/dev schema migration,
SQLite mutation, commit or push. The stopped local PostgreSQL lab was started
on loopback25432; generated test schemas were removed by their fixtures.

No gameplay route was enabled. Publication remains denied; mob/skill/buff/item
reference validation, drop semantics, authoritative battles, legacy migration,
native protocol integration and APK smoke are still required.
