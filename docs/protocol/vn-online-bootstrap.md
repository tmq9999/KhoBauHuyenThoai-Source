# Authored online inventory bootstrap contract

This M2 adapter is a new local server contract, not a recovered historical
provider API. It serves the PostgreSQL inventory slice only. The recovered APK
still needs complete player-entry/login wiring before automatic activation;
an inventory response must not be passed off as a full native player snapshot.

Pinned source references (`project.js` SHA256
`9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818`):
`serverMain.register/login/getServerInfo` at51711ff submit URL-encoded fields
to `/user/register`, `/user/login`, `/user/serverInfo`. Socket gate/connector
selection at53950ff is a separate bootstrap flow. The `/v1` JSON API below does
not pretend to be wire-compatible with those builders. Adapting those exact
consumers and complete player entry remains required before native activation.

## Scope and authority

`serve-bootstrap` is an opt-in loopback listener, separate from `serve` and
`serve-inventory`. It creates accounts/sessions, not players, wallets, items or
published releases. No automatic migration, SQLite token conversion or dual
write. Authentication uses Argon2id for new hashes and upgrades valid existing
scrypt hashes after successful password verification. Unknown hash schemes fail
closed; legacy SQLite password migration remains a separate rehearsal.

The implementation plan defines these endpoint boundaries:

| Method/path | Input | Output purpose |
| --- | --- | --- |
| POST `/v1/accounts` | login/password JSON | Account UUID, no automatic session |
| POST `/v1/sessions` | login/password JSON | Bearer token and expiry duration |
| DELETE `/v1/sessions/current` | Bearer authorization | Revoke current session |
| GET `/v1/players` | Bearer, bounded pagination | Only owned player summaries |
| POST `/v1/inventory/bootstrap` | Bearer, playerId/serverId | Existing bridge hello and replacement bag snapshot |

Bootstrap selects the server's active published content rather than trusting
caller-provided content, identity or inventory provenance. It returns the
configured loopback inventory URL, `inventoryIdentity: "postgres-v1"`, existing
inventory hello and `fullPlayerSnapshot: false`. The token is not echoed in
bootstrap. The consumer supplies its in-memory login token to the WebSocket
handshake; never store it in URL, manifest, source bundle or logs.

## Local safety contract

Bodies are bounded to4096 bytes. Credentials/selection reject extra fields,
bool-as-int IDs and malformed JSON. Validation and unexpected errors expose
fixed codes, never raw request input, passwords, tokens, SQL or stack traces.
Responses use no-store. Browser Origin requests and credential-query strings
are denied; no cookies/CORS and no trusted forwarded-client-IP header.
The body reader uses a5-second total deadline, including deferred header-error
handling; incomplete requests receive a fixed timeout response. Duplicate JSON
keys and nonfinite constants are rejected before DTO parsing.
Rate and concurrent password-hash limits are bounded process-local controls,
not distributed production defenses. Runtime credential provisioning, HTTPS,
full native bootstrap and online-service acceptance remain separate gates.

The configured lab hash policy accepts Argon2id v19 with memory8192..65536KiB,
time1..3, parallelism1..4,16-byte salt and32-byte hash; supported older settings
rehash after verification. Out-of-policy stored hashes fail closed, avoiding
unbounded KDF allocation from corrupt rows. New hashes use the pinned library's
64MiB/time3/parallelism4 profile. The legacy scrypt reader accepts only its exact
scheme with16-byte salt/64-byte digest, not arbitrary prefixes.

## Verification distinction

Tests must use real loopback HTTP, PostgreSQL and existing Pomelo inventory
transport, with explicit test-only players/content/opening inventory. A successful
login/bootstrap/useItem test does not establish organic box acquisition, new
player creation, native UI boot, online deployment or playable full-game support.
Execution evidence belongs in `docs/agent-runs/online-server-progress.md`.

## Dependency references

Environment: Python3.12, FastAPI0.141.1/Pydantic2.13.5 and argon2-cffi25.1.0.
Context7 was unavailable in the implementing session. Official documentation
read on2026-09-17:

- https://github.com/fastapi/fastapi/blob/master/docs/en/docs/tutorial/handling-errors.md
- https://github.com/hynek/argon2-cffi/blob/main/docs/howto.md

FastAPI validation errors can retain raw request bodies, so this boundary must
use its own fixed JSON error handler. Argon2 verification raises typed mismatch/
invalid-hash exceptions; successful checks may require rehashing. Neither
raw validation errors nor stored password hashes belong in diagnostics.
