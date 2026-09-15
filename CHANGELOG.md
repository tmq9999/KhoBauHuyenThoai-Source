# Changelog

All notable project changes are recorded here. Dates use `YYYY-MM-DD`.

## [Unreleased] - 2026-09-16

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
