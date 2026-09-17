# Dependency archive checkpoint — 2026-09-16

Status: bounded M1.2 archive/reference audit SERVICE_TESTED. Actual content
report BLOCKED; no native gameplay, content publication or online acceptance.

## Deliverables

- `content/source.py`: safe ordered literal archive with !0/!1 normalization.
- `content/dependencies.py`: normal-map transitive mob/skill/buff reference audit,
  summoned mob traversal and equipment/consumable entity references.
- `content/archive.py`: immutable exact-replay-checked PostgreSQL persistence.
- `0010_dependency_archives` migration and `import-dependencies` CLI.
- New parser/audit tests and PostgreSQL archive/CLI tests.
- README, CHANGELOG, backend README, source evidence, plan/runbook/progress synced.

All seven tables retain original headers, row order and sparse cells. Source
counts:16,245 mobs;474 skill rows;745 buff rows;1,812 entities;120 equipment
recipes;7 consumables;379 drop rows. Duplicate rows are not overwritten.

## Evidence and tests

RED:9 parser tests,12 audit tests,7 database tests before their implementations.
Concurrent insert additionally exposed a primary-key race; broad ON CONFLICT
handling and exact persisted-bundle verification resolved it. No exception is
silently interpreted as gameplay success.

- Full online suite:250 passed in117.95s.
- Full recovery/protocol:326 passed,4 Windows symlink skips in113.82s.
- Archive suite after two extra coverage cases:9 passed in17.64s. These were
  added after broad online discovery; production code was unchanged.
- compileall, pip check and git diff --check passed.
- Independent scoped reviewer: no Important/Critical findings; minor mismatch
  coverage suggestion implemented as a real PostgreSQL test.

Source SHA256 and APK SHA256 remain respectively
`9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818` and
`d61d4ae1994ec5bcafdcfaf2406cc88ed9611cbb65da853027799d50d6687eb4`.

## Blockers and scope

Skill1105010 has conflicting rows466/467; buff10006 has rows6/7. The former
is reachable through normal-map child-skill references. Report explicitly returns
two DUPLICATE_ID plus one AMBIGUOUS_REFERENCE, and publishable=false.
See [consumer evidence](../protocol/vn-combat-content-dependencies.md).

No normalized combat rules were promoted from ambiguous rows. Drop weights,
combat numbers/effects, recipe cycles/acquisition, other modes and native
acceptance are pending. Next: comparator/native conflict-policy evidence.

Work is uncommitted. Test mutations were confined to generated `kbht_test`
schemas; no development/production migration, SQLite/player mutation, APK
installation/launch, provider traffic or push occurred.
