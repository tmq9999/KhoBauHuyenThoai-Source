# Changelog

All notable project changes are recorded here. Dates use `YYYY-MM-DD`.

## [Unreleased] - 2026-09-16

### Inventory and reward transaction foundation

- Added owned inventory stacks, quantity/version constraints and append-only
  item ledgers. Domain commands can add/split/refill or consume a specific owned
  record; insufficient quantities roll back the complete transaction.
- Added reward-source deduplication across command IDs, item/currency grant
  history, and transactional `reward.granted` events. Reusing a source with
  different reward data fails instead of silently granting extra assets.
- Added additive migrations `0003_inventory_rewards` and
  `0004_content_immutability`, plus item/reward reconciliation checks; published
  content cannot be switched back to draft to edit item rules.
- Extended `pg_lab` with actual inventory/ledger queries and opening commands.
  This provides service-level persistence, not new native gameplay routes or
  an acquisition path for evolution materials. API usage is in
  `server-online/README.md`.

### Runtime privileges and durability checks

- Added `grant_runtime_access` for a dedicated non-owner role with explicit
  table/column grants; rejects superuser, inheritance, object ownership and
  pre-existing excessive privileges instead of silently retaining them.
- Added migration `0005_runtime_guards` to freeze game-server identity while
  allowing the column permission PostgreSQL requires for row locks. Runtime
  cannot read password hashes, rewrite history/ownership/content or run DDL.
- Added abrupt-process-loss tests before and after command commit and a
  `pg_dump`/`pg_restore` round trip of generated test schemas. The tests verify
  inventory, reward, wallet, command replay and worker dedup survive restoration.

### Leased outbox worker and Compose model

- Added persisted outbox delivery leases with `SKIP LOCKED`, immutable retry
  budgets, stale-worker fencing, bounded backoff and dead-letter quarantine.
  Direct consumers and pollers share one receipt transaction; terminal deliveries
  cannot be reopened or bypassed.
- Added poller tests covering concurrent claims, lease expiry, direct races,
  handler/database failure, process restart and poison events.
- Added digest-pinned loopback Compose model for PostgreSQL 18 dev/test and
  ephemeral Redis 8.2.9 with file-based secrets. Compose CLI validation passes;
  Docker Engine is not installed on this development machine, so container
  health is not claimed.
- Added delivery reconciliation invariants and race tests: completed receipts
  win over stale leases, direct delivery cannot bypass dead-letter quarantine,
  and failed receipt/projection transactions retry without duplicate state.

### Technical documentation and outbox consumption

- Reorganized the root and backend READMEs into architecture, module/data
  reference, configuration and usage guides. Session test results, temporary
  blockers and installation evidence stay in `docs/agent-runs/`.
- Added `OutboxConsumer.consume(event_id)` with atomic per-consumer receipts:
  duplicate concurrent delivery applies a database projection once, and handler
  failure rolls back both acknowledgement and projection. See
  `server-online/README.md` for the handler contract and error semantics.
- Added additive migration `0002_worker_receipts`, preserving the frozen core
  revision and existing ledger/command data; outbox events and receipts reject
  updates, deletes and truncation.
- Added a two-account `pg_lab` fixture with real opening ledger entries,
  stable command IDs and cross-account denial tests. Projection counters and
  purchase prices used by the fixture remain test-only, not game features.

### M1 environment preparation

- Created a Git-ignored, isolated `server-online/.venv` with the existing
  Python 3.12.9 and bundled pip 24.3.1. Verified global packages are excluded;
  no global Python, PATH, Windows service or existing game state was changed.
- The first PostgreSQL download attempt was blocked by the approval service's
  provider-credentials 404. It completed after the owner enabled network access;
  the initial failure is retained in the progress log.

### M1 database foundation

- Installed PostgreSQL `18.6` as a portable, loopback-only cluster on port
  `25432`, with isolated `kbht_test` and `kbht_dev` databases; no Windows
  service, global PATH change or existing SQLite/MuMu data was touched.
- Installed the pinned M1 Python stack into `server-online/.venv` and generated
  hash-locked `server-online/requirements.lock`.
- Added the initial authoritative schema, migration/CLI commands, typed command
  receipts, double-entry wallet postings, outbox events and replay-safe
  transaction boundary. Added 44 tests: 34 real-PostgreSQL checks and 10
  configuration/CLI checks; none skipped in the local verification.
- Documented exact provenance, local hash, start/stop, migration and test
  commands in `server-online/README.md`.

- Isolated the legacy ZIP validator's filesystem test from the running
  PostgreSQL data directory. The recovery suite again passes 266/4 skipped.
- This is a partial M1 slice, not completed M1: inventory/rewards, outbox worker
  deduplication, restricted runtime roles and database restore rehearsal remain.

### M0 implementation

- Added a non-executing, hash-pinned RPC inventory CLI with read-only check,
  guarded update and duplicate call-site preservation; extracted 230 routes.
- Mapped 77 CORE routes to reviewed response consumer profiles, including
  explicit unresolved-schema gates rather than invented success payloads.
- Added opt-in staged power display formatting for fractional sums in home,
  role/team and rank UI. Signed APK packaging is verified; native smoke is not.
- Added missing snapshot purchase/draw counters while preserving existing
  player balances, inventory, roles and counters in the SQLite migration.
- Added per-commit README/CHANGELOG enforcement and SHA-pinned CI actions.
  Portable schema fixtures and temporary test roots replace dependencies on
  private lab artifacts for ordinary tests; native-input tests remain explicit.
- Paused new remote pushes after identifying historical SDK secret-shaped
  literals in the recovered source. No values were used or copied to the new
  artifacts; no repository history, original APK or pinned source was rewritten.

### Added

- Added an owner-approved design for a PostgreSQL-authoritative online game
  server, protocol adapters, economy ledgers, live operations and admin panel.
- Added the Codex execution runbook with milestone gates, database rules,
  native MuMu verification and commit documentation policy.
- Added a detailed defect/route matrix for power formatting, map progression,
  battle abilities, equipment, friends, tasks, Beli purchases and events.
- Included the existing lab feature slice in the source snapshot: six-stage
  settlement, derived role fields, inventory use/sell/EXP, sign-in and green
  evolution with regression tests. This is not full-game compatibility.
- Included sanitized native callback diagnostics and their regression tests;
  APK source and previous recovery evidence remain unchanged.

### Changed

- Moved implementation handoff from Antigravity to direct Codex execution;
  Antigravity recovery notes remain historical evidence.
- Defined README and CHANGELOG updates as a requirement of every deliverable
  commit.
- Corrected README's active APK/manifest reference to the lab artifact installed
  on 2026-09-16 and documented the remaining native gameplay failures.
- Connected the existing Git history to the owner-created private repository
  `tmq9999/KhoBauHuyenThoai-Source` without reinitializing or rewriting commits.
- Excluded runtime databases, signing material, environment secrets and local
  test caches from future staging; no local data was removed.

### Known Limits

- The source snapshot and handoff do not implement the proposed production
  database, admin panel or complete online game.
- The existing `server-compatible/` runner remains a lab compatibility slice;
  native gameplay and production payments are separate acceptance gates.
- Private repository visibility and Git access were verified on 2026-09-16
  after the earlier authentication/approval blocker cleared. Source backup
  does not imply approval to deploy or expose the game service.

### Verification

- M0 local suite: 266 passed, 4 skipped; formatter Node test: 1 passed.
- Opt-in power-display APK built/signed and decoded payload matched stage;
  source APK/project hashes preserved. No install, live DB change or push.
- Re-ran the scoped existing suite on 2026-09-16: 215 passed, 3 skipped.
- Checked all 23 local links in the seven handoff documents and parsed the
  12 Python examples/JSON snippets. No native gameplay acceptance is claimed.

## Recovery baseline - 2026-09-14 to 2026-09-15

### Recorded history

- `4129693`: initialized the APK recovery project and retained source provenance.
- `2066351`, `f25b368`: added tutorial recruitment and completion-marker repairs.
- `5fa53c8`: serialized player normalization with concurrent SQLite mutations.
- `e1a2045`: added first-SMAP battle begin/settlement compatibility.

This snapshot also includes the later feature-slice work reported in
`docs/release/2026-09-15-server-feature-slice.md`; it is not represented as a
released production build here. Existing report/test numbers are historical,
not fresh verification of every native feature.
