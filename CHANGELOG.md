# Changelog

All notable project changes are recorded here. Dates use `YYYY-MM-DD`.

## [Checkpoint] - 2026-09-17

### Online backend delivery documentation

- Added a dedicated Antigravity handoff with a copy-paste continuation prompt,
  read order, T01/T02 starting points and repository-backed progress checkpoints.

- Added the owner-requested APK-derived online backend spec, 20-task execution
  plan and operational runbook, grounded in checkpoint990d8dc.
- Reconciled stale battle/settlement status and identified actual production
  gaps: loot semantics, wider role stats, durable native commands, local-only
  database/gateway/client configuration and release operations.
- Routed active instructions to the new set. No Lab/emulator/ADB or broad test
  loops; existing evidence remains historical and owner APK acceptance is separate.
- Documented proposed production commands as unimplemented interfaces, not
  runnable deployment instructions. No service/device/DB change in this update.

- Preserve the accumulated PostgreSQL content/auth/player/tutorial/inventory
  implementation, native client staging patches, documentation and existing checks.
- Include durable native SMAP sessions, frozen submissions, authoritative reports,
  ledger settlement and source-derived AP/XP recovery changes through migration0016.
- Include NativeBattle staging with battle/scene identity and copied request scope.
- This is a source snapshot, not an online release or a native battle acceptance.
  No tests, emulator, database activation or APK build were run for this commit,
  as requested by the owner. Ignored secrets/runtime artifacts remain local.

## [Unreleased] - 2026-09-16

### Recovered combat implementation (2026-09-17)

- Added a source-pinned45-module battle extractor and bounded isolated runner
  using recovered AI/action/formula/buff/scheduler/RNG code, not auto-win logic.
- Added map/role combat dependency closure, strict ambiguity refusal and an
  explicit client-lookup compatibility policy retaining both duplicate records.
- Added ordered end-tick manual skill inputs with ownership/MP/cooldown guards.
  Report hashes bind input/artifact/results; no client star is trusted.
- Added an unstaged ES5 battleId/seed/action recorder with frozen settlement
  retries and stale-battle identity guards; native scene hooks remain pending.
- Native battle bridge, persistent settlement/rewards and map10107 acceptance
  remain unfinished; computation results do not unlock stages or mint loot.

### Native opening activation preparation (2026-09-17)

- Added explicit native-opening-v1 policy for the proposed role-level power
  argument, initial skill100101 level1, skill cap15 and unavailable class63.
- Added SHA-pinned native metadata/config/notice serving in serve-native on20001;
  no compatibility runner or general file server is required.
- Backed up empty-player kbht_dev before additive0014 migration; checked all
  ledger invariants afterward. No existing SQLite player state was converted.
- Activated the scoped opening release and verified actual APK register/login/
  create/home/first rename against PostgreSQL using a restricted runtime role.
  Recruitment/battle/map1-7 are not included in this native opening milestone.
- Added source-backed once-only tutorial recruitment implementation for Zoro/
  Nami, new immutable tutorial release and scoped opening-player migration path;
  general paid/free repeated/ten draws remain unavailable.
- Activated0015 tutorial release with backup and preserved one existing player;
  actual APK showed Zoro/Nami and PostgreSQL persisted exactly two tutorial claims.

### Native persisted starter implementation (2026-09-17)

- Added normalized native player/profile/role/skill/equipment storage and
  source-pinned immutable starter definitions in additive migration0014.
- Added atomic create/replay, compressed native entry snapshot, one-time first
  rename and ledgered AP/skill recovery. No SQLite fallback or fabricated catalog.
- Ambiguous opening rules require explicit versioned policy; no active release
  is automatically published and no native gameplay acceptance is implied.

### Native-client-first execution reset (2026-09-17)

- Added the owner-requested replacement spec, plan and runbook with native
  10106->10107 acceptance and explicit PostgreSQL-only gameplay requirements.
- Updated active project routing to the new execution set; preserved older
  artifacts and database/security requirements rather than deleting history.
- Began source-backed `/user/*` and native Pomelo adapter implementation; a
  standalone `/v1` or SQLite tutorial result no longer counts as product delivery.
- Added PostgreSQL native form authentication, standard gate/connector handshake,
  authenticated owned-player listing and combined `serve-native` lifecycle.
  Full native snapshot/create/entry and gameplay are explicitly unavailable.
- Added opt-in NativeAvailability staged consumer guards for unavailable server
  lists, failed gate/connector binding and genuinely absent shop/card catalogs;
  no fabricated products or player state. Inventory-only bridge mode stays separate.

### Native lab execution (2026-09-17)

- Installed the inventory-bridge APK by data-preserving upgrade on the named
  KBHT-Online-Lab MuMu instance; verified installed SHA256 and retained first
  install time. Original installed APK and SQLite backup retained privately.
- Observed native registration/login, server selection, tutorial Luffy and home
  rename UI against the existing SQLite compatibility runner. PostgreSQL native
  activation is not claimed; no public deployment or physical-device action.

### M2 account and inventory bootstrap (2026-09-17)

- Added hash-pinned Argon2id dependency for the opt-in online
  account/bootstrap boundary; existing package versions remain unchanged.
- Added account ACTIVE/LOCKED status through additive migration0013, durable
  session lock checks and successful-login upgrade of existing scrypt hashes.
- Added opt-in loopback `serve-bootstrap` for registration, login, logout,
  owned-player listing and inventory-release selection. Bounded JSON, fixed
  redacted errors, no-store replies and auth concurrency limits apply.
- Documented the separate authored `/v1` bootstrap contract and remaining
  native `/user/*`/player-entry integration boundary. No automatic cutover.

### Native inventory packaging continuation (2026-09-17)

- Added opt-in staged bridge/socket integration to the recovered APK builder;
  activation requires trusted PostgreSQL identity and fences the legacy writer.
- Fixed duplicate native error notifications using the bridge error channel;
  added real-bridge/copied native-consumer coverage for bag updates and rewards.
- Integration staging now requires an explicit root and rejects escaping paths,
  reparse points and multiply-linked destinations before writing.
- Kept the real socket/Node/PostgreSQL E2E in the backend test suite and archived
  the obsolete root-suite duplicate so recovery collection needs no backend DB.
- Corrected documentation to distinguish the inventory-only Pomelo listener,
  packaged hook and still-missing full online bootstrap/native acceptance.
- Built and payload-verified signed lab artifact
  `20260916T190803Z-repack` with InventoryBridge; APK SHA-256 is
  `afc37cc3fb77846c6e477fa6c507110e7405f9754c53d8f159a2542abddbd79c`.

### Loopback Pomelo inventory transport and client bridge

- Added explicit `serve-inventory` WebSocket/Pomelo listener backed by the
  negotiated PostgreSQL command boundary, with bounded work and strict framing.
- Added source-provenance codec copy, sanitized failure/cleanup paths and
  canonical WebSocket-length rejection; no runtime dependency on SQLite runner.
- Added standalone ES5 inventory bridge with action queue, exact replay on
  reconnect, replacement snapshots and conflict resync. Opt-in staged integration
  is described above; full native login/gameplay support remains incomplete.
### Negotiated inventory connection state

- Added per-connection token/capability/player/content negotiation, revalidation
  before commands and replacement bag snapshots for reconnect/resync.
- Failed renegotiation clears prior identity; commands cannot switch selected
  scope. Reconnect preserves original command IDs/versions for durable replay.
- Added expiry/revoke/rotation, cross-account, stale-state and concurrent-close
  tests. No listener, default gameplay route or fabricated full player bootstrap
  is introduced; admitted operations are not forcibly cancelled by later revoke.
### Native inventory DTO boundary

- Added opt-in capability-gated native useItem payload translation, stable
  fresh-online bag IDs, bag deltas/tombstones and reward popup fields.
- Saves translated responses inside the command receipt transaction; later
  retries cannot reflect unrelated newer inventory. Added scoped consistent
  snapshots with ownership, release and unsupported-metadata checks.
- Verified PostgreSQL and authenticated HTTP behavior, not native runtime.
  Legacy bag migration, transport negotiation, full snapshots and acquisition
  remain pending; default gameplay exposure is unchanged.
### Atomic fixed material-box consumption

- Added source-verified fixed fragment-box staging and migration0012 with
  versioned recipe foreign keys and published-content mutation guards.
- Added an owned-inventory box-use command: consume and grant rewards share the
  existing transaction, item ledgers, receipt and outbox. Retries cannot duplicate
  rewards; failed grants restore the consumed box through rollback.
- Added core inventory snapshots/tombstones, batch validation, runtime read-only
  content grants, concurrency and authenticated HTTP service tests. This is not
  a native bag adapter or a box-acquisition implementation; default routes stay
  disabled and no live/player data was seeded.
- Added before/after-commit process-loss tests and reward-capacity rollback
  coverage for fixed-box commands; test children only target isolated schemas.
### Material source and drop structure audit

- Added strict fixed/random descriptor parsing with separate weight/rate fields,
  drop-class/box reference and cycle validation, and per-material static sources.
- Added `audit-acquisition` using immutable PostgreSQL snapshots and exact
  replay/concurrent deduplication. Existing dependency archive behavior retained.
- 177 zero-count rows remain unresolved;78 materials have static candidates, not
  verified gameplay sources. No inventory grant or gameplay route is enabled.
### Equipment recipe drafts

- Added validated equipment evolution/material graphs and atomic PostgreSQL
  `prepare-equipment` drafts via migration `0011_equipment_content`.
- Preserves source snapshots and target-tier costs; rejects invalid references,
  quantities, cyclic recipes and replay drift. Published projections are guarded.
- Combat duplicate IDs remain unresolved. No upgrades, inventory grants,
  acquisition rules, server activation or APK gameplay acceptance are implied.

### Combat/item source archives and reference audit

- Added safe !0/!1 literal handling and an ordered archive preserving sparse
  fields, sentinel ID0 and duplicate rows without executing recovered JS.
- Added transitive normal-map mob/skill/buff reference checks and equipment
  recipe/consumable entity checks, including summoned mobs and child skills.
- Added immutable PostgreSQL migration `0010_dependency_archives` and
  `import-dependencies` CLI with exact replay checks and concurrent deduplication.
- Reported conflicting source skill1105010 and buff10006; skill1105010 is
  reachable from normal maps. No last-wins rule, reward or gameplay success is
  invented. Archives may store blocked evidence; publication remains disabled.

### Normal-map content drafts

- Added explicit sparse chapter parsing and chapter-based normal-map ordering,
  including stage 10107 and the transition from chapter 1 to chapter 2.
- Added migration `0009_normal_maps` for chapter provenance, versioned map
  definitions and ordered mob-wave references. Preparation is atomic and
  replay-checked; published projections reject changes. Existing smap-only
  imports can backfill chapters from the same hash-verified source.
- Raw drop values are preserved without inventing reward quantities. Full
  mob/skill/item validation, battle simulation, publication and APK gameplay
  acceptance remain pending; no existing player data is migrated or rewritten.

### Transport documentation correction

- Clarified the existing loopback HTTP command transport and durable session
  service. HTTP register/login endpoints are not implemented; account operations
  are Python-only and native authentication remains pending. Removed the
  unsupported endpoint/test-count claim from the previous draft documentation.

### Draft content release boundary

- Added replayable PostgreSQL draft preparation and CLI roundtrip tests.
- Removed automatic server opening from source publication: raw APK tables are
  not validated gameplay releases. Draft replay rejects changed release hashes.
- Native gameplay, session service and release activation remain incomplete.

### Online command boundary

- Added strict command-envelope validation and explicit route allowlisting
  before the PostgreSQL executor; account identity cannot come from wire fields.
- Added real-database tests for replay, wrong ownership and invalid envelopes.
  The test purchase is internal, not an exposed gameplay route. Session
  authentication, HTTP/Pomelo listeners and native verification remain open.

### Online content preparation

- Added hash-verified non-executing APK table reader and in-memory map release
  preparation, with source and importer tooling tests including stage 10107.
- This is not PostgreSQL content publication, graph validation or native map
  acceptance. No running server or player state is changed by these helpers.

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
