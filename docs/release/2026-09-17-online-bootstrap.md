# Loopback auth and inventory bootstrap checkpoint

Scope: authored PostgreSQL M2 service/HTTP adapter, not full native login,
historical provider protocol or public deployment. Existing APK remains
`20260916T190803Z-repack`; no new client build or device action in this slice.

## Delivered interfaces

- Argon2id account registration, strict recognized scrypt verification and
  successful-only upgrade, bounded stored KDF work factors.
- Migration0013 adds ACTIVE/LOCKED without rewriting credentials/session rows.
  Locked accounts cannot authenticate, issue or resolve sessions.
- `serve-bootstrap` on loopback21003: accounts, sessions, logout, owned player
  pagination, inventory bootstrap using server-selected published content.
- Bootstrap returns postgres-v1 identity, exact inventory hello and bag-only
  snapshot. It never grants items or creates player/gameplay state.
-4096-byte/5-second body bounds, duplicate/nonfinite JSON denial, fixed errors,
  no-store, no browser Origin/cookies/access logs, bounded global auth attempts
  and hash concurrency. These are local controls, not internet readiness.

## Evidence

Task6 focused HTTP/DB/session/migration suite:74 passed42.27s, no skips.
Real socket test registers/logs in, selects a test-owned player, negotiates
Pomelo and consumes a fixture box; exact replay produces one receipt with
conserved ledgers. Seeded box data is test-only, not an acquisition route.
Migration, revocation during snapshot, concurrent password changes, body
timeout/chunked limits and redacted unexpected errors have targeted evidence.

Recovery/protocol393 passed9 Windows symlink skips115.89s; Node21 passed.
Wheel includes service, HTTP adapter and migration0013. CLI help, pip check,
compileall and diff checks pass. Full backend379 passed195.69s (379 collected
after freeze). Independent review: spec PASS, quality APPROVED; no Critical or
Important finding in loopback scope. Minor deferred: pagination test with two
owned players and non-null nextAfter; no native/public acceptance implied.

## Remaining gates

No schema migration on kbht_dev, no source upload, no listener deployed for
players, no SQLite conversion and no native acceptance. Auth runtime-role
provisioning remains separate from gameplay role. Unknown-login timing and
duplicate-registration enumeration are not concealed; TLS/distributed abuse
defense are absent. Do not expose this lab adapter publicly.

Next M2 work is complete source-backed player creation/entry and native
`/user/*` login-consumer integration. Current `/v1` responses cannot replace
the full player snapshot. Organic acquisition/content publication, legacy
reconciliation and isolated native smoke remain open.
