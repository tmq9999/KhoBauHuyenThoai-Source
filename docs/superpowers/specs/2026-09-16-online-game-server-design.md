# Kho Báu Huyền Thoại Online Server Design

**Status:** Owner-approved architecture direction; executable Codex handoff.
Detailed defaults below are explicit engineering proposals. M0 records any
owner-requested changes; cash-out and production exposure remain separate gates.

**Runbook:** [Codex execution](../runbooks/2026-09-16-codex-online-game-server.md)

**Plan:** [Milestones and first execution batch](../plans/2026-09-16-online-game-server.md)

**Review:** [Route/defect matrix](../../protocol/vn-online-route-matrix.md)

**Owner outcome:** The recovered APK must play against an authoritative server
whose database, protocol adapter, battle rules and administration tools can be
operated as an online game service. A passing unit test or a repacked APK is not
gameplay acceptance.

## Scope

This design replaces the current compatibility-only runner in stages. The
existing `server-compatible/` remains a protocol laboratory and migration
reference until each route has a production replacement. The immutable APK,
decoded source evidence and previous run artifacts remain unchanged.

### Player-facing capabilities

The first production slice must cover the complete first-session loop:

1. Local account registration/login, server list, session and reconnect.
2. Player creation, rename, avatar/ship selection and home bootstrap.
3. Role roster, role stats, power calculation, levels, EXP, skills and team
   formation.
4. Equipment inventory, equip/unequip, level upgrade, material consumption,
   evolution, role star and role evolution where the APK contract is known.
5. Map unlocks, map attempts, authoritative battle simulation, abilities,
   result report, AP/EXP/coin rewards and idempotent settlement.
6. Inventory stacking, box/AP/EXP item use, selling and item provenance.
7. Sign-in, daily tasks, task claims, activity definitions and activity claims.
8. Friend search/request/accept/remove, gift send/receive and friendship stats.
9. Beli purchase using gems with server-side pricing, daily limits and ledger.
10. Notices, system mail, gift codes, top-up reward records and claim history.

Arena, guild, expedition, practice, world-boss and other modes use the same
domain contracts after the first-session slice is stable. They are not allowed
to bypass the battle, reward or currency services.

### Administration capabilities

The admin surface is a separate authenticated application and API. It must
provide:

- User/player lookup, account status, session revoke, ban/unban and support notes.
- Read-only player timeline and controlled corrections through audited commands.
- Item/role/currency grants and removals using a signed reason and immutable
  ledger entry. Direct payload editing is prohibited.
- Map/config and drop-table publishing with version, preview and rollback.
- Notice/mail management, audience targeting, schedule and delivery status.
- Event/sign-in/task creation, activation window, reward preview and claim audit.
- Top-up order reconciliation, reward packages, refund records and withdrawal
  request review. Real money providers are behind an adapter and disabled in lab.
- Audit search, export and operational health (sessions, queue, errors, backups).

## Non-goals and safety boundaries

- No historical provider, payment or analytics endpoint is contacted.
- No real-money withdrawal is enabled until a provider contract, legal policy,
  reconciliation and manual approval flow exist. Lab withdrawal requests remain
  non-payable records.
- No server trusts client-reported power, battle outcome, drop list, price or
  currency balance.
- No opaque JSC blob is treated as recovered source. Static APK data is imported
  through a non-executing parser with source hash and provenance.
- No migration overwrites the existing SQLite state. A one-way import creates a
  new database and a reconciliation report.

### Implementation stack and alternatives

Default: keep Python 3.12 for core/services/worker and reuse the verified Pomelo
codec. Add FastAPI for HTTP/admin, SQLAlchemy 2 + Alembic + psycopg 3 for PostgreSQL,
Redis for ephemeral state, React + TypeScript + Vite for the admin UI. Deployment
starts as one modular backend and one worker; it is not microservices-by-route.
Pin tested patch versions and image digests in M1/M8, not unverified `latest`.

Alternative A, continuing JSON SQLite indefinitely, cannot deliver the required
cross-player/ledger/admin invariants. Alternative B, a TypeScript rewrite of the
entire backend, adds migration cost before validating missing gameplay. Select
the Python modular monolith by default; any language switch requires an ADR and
owner approval. The Cocos native client/engine is retained in every option.

Context7 is not callable in this session. Dependency/CLI documentation must be
fetched at the implementing milestone (or official versioned docs when unavailable).
No dependency was installed or version compatibility tested by writing this spec.

## Architecture

```text
Recovered APK
    |
    | Pomelo/WebSocket + bootstrap HTTP
    v
Protocol adapters  <-->  Session/auth service
    |                         |
    v                         v
Game application services --> PostgreSQL (authoritative state)
    |                         |
    +--> Redis (presence, rate limits, short-lived locks)
    +--> Outbox --> workers --> notices/mail/payment adapters
    |
    +--> Battle engine (deterministic, versioned rules)

Admin web UI --> Admin API --> same services + audit log
```

### Service boundaries

- **Bootstrap adapter:** config, notice, manifest and account HTTP response
  shapes required by the APK. It never mutates game state.
- **Gateway/session:** Pomelo framing, handshake, heartbeat, route dispatch,
  authentication, reconnect and request idempotency. It passes typed commands
  to services and returns typed response envelopes.
- **Player service:** player identity, profile, team, progression and snapshots.
- **Role/equipment/inventory services:** all ownership and stat mutations.
- **Battle service:** map validation, team reconstruction, ability execution,
  deterministic report and reward settlement.
- **Economy service:** balances, purchases and ledger entries. Every debit and
  credit is paired, attributable and idempotent.
- **Activity service:** versioned definitions, schedules, progress and claims.
- **Social service:** friends, gifts, friendship attributes and notifications.
- **Admin service:** RBAC, command validation, audit and support workflows.
- **Content service:** imports APK tables into versioned relational content;
  published versions are immutable.

Each service exposes input/output schemas. Internal code receives validated
types; boundary errors use one envelope:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request",
    "details": {}
  },
  "requestId": "00000000-0000-4000-8000-000000000001"
}
```

Pomelo compatibility responses keep the APK's `{code, msg, _temp}` fields at
the adapter boundary, while the core uses typed errors and never leaks SQL,
stack traces or provider credentials.

### Command and response contract

Every mutating core command carries `command_id` (UUID), `account_id`,
`player_id`, `server_id`, `route`, `expected_version`, `content_version_id` and
validated `payload`. `command_id` is generated once per user action and reused
after timeout/reconnect. A Pomelo transport request ID alone is not durable
idempotency: it can change across reconnect and must never be used as a purchase
deduplication key by itself.

Legacy client support: M0 maps the socket wrapper; M2 adds an explicit
capability-negotiated command ID/version field at that single boundary, kept in
the client retry queue. Updated adapter accepts it; legacy adapter rejects
unsupported mutations explicitly. Do not break existing strict body-key
validation without versioning the adapter and rebuilding/testing the matching
APK. On response loss the client retries/query-statuses the same command; it
does not create a fresh paid action.

Core returns `command_id`, `aggregate_version`, `content_version_id`, immutable
`result` and committed event IDs. Replaying a committed command returns its
saved result; same key with a different payload hash returns `CONFLICT`.
Client applies deltas only in version order; gaps trigger a full snapshot so a
stale response cannot roll back inventory or wallet UI. Whole role records and
map subtrees follow `player.update` semantics; item removals use null tombstones.

### Numeric and time contract

- Money/inventory: integer units only; SQL BIGINT and non-negative bounded
  balances. API UUID/BIGINT identifiers are strings in admin JSON; legacy wire
  IDs are stable safe integers (`<= 9007199254740991`).
- `power_milli`: integer thousandths calculated from decimal content values;
  public `power` is `floor(power_milli / 1000)`, chosen as the new server display
  policy. Store calculation/rules version. Client formats total sums too;
  test `980.2 + 980.2 + 978.2` and the owner's `3873.0999999999999` case.
- Default aggregate policy: home/total-roster rank sums owned roles; selected
  battle team sums only its selected roles. Sum `power_milli` before flooring,
  never sum individually truncated UI strings. Enhanced snapshots expose the
  integer milli-value for client selection arithmetic; stale totals trigger a
  refreshed snapshot. This is an explicit new server rule, not historical proof.
- Calculated role power includes level/equipment/skill/passive/awake/friendship
  terms specified by a published formula; the current guessed second argument
  to getPower must be resolved or explicitly approved, not called historical.
- UTC storage (`timestamptz`), business zone `Asia/Ho_Chi_Minh`. Sign-in flips
  at 00:00; APK daily reset is 05:00; weekly boundaries are Monday at 05:00.
  Each definition stores reset policy. No reliance on the host's timezone.
- Account/server scope is explicit. New public player IDs start above 10000
  because `project.js:49558` identifies IDs <=10000 as robots. Legacy IDs get a
  durable mapping applied to friend/team/mail references and client storage.

## Authoritative data model

PostgreSQL is the production source of truth. UUIDs identify accounts,
sessions, orders and audit records; integer content IDs remain compatible with
the APK. Every mutable aggregate has `version`, `created_at`, `updated_at` and
an audit/outbox path where applicable.

### Identity and access

- `accounts(id, login_name, password_hash, status, created_at, updated_at)`
- `sessions(id, account_id, player_id, token_hash, expires_at, revoked_at,
  last_seen_at, client_version)`
- `players(id, account_id, server_id, name, level, experience, power_milli,
  action_point, skill_point, version, created_at, updated_at)`
- `admin_users`, `admin_roles`, `admin_user_roles`, `admin_audit_logs`

### Content and progression

- `content_versions`, `roles`, `role_skills`, `skill_buffs`, `items`,
  `equipment_recipes`, `experience_levels`, `maps`, `map_waves`,
  `drop_tables`, `drop_entries`, `published_configs`
- `player_roles(player_id, role_id, level, star, awake_level, experience,
  power, version)`
- `role_equipments(player_role_id, slot, item_id, level, attrs_json)`
- `teams(player_id, slot, version)`, `team_members(team_id, position,
  player_role_id)`
- `inventory_items(player_id, item_id, quantity, metadata_json, version)`

### Economy and rewards

- `wallets(player_id, currency, balance, version)`
- `wallet_ledger(id, player_id, currency, delta, balance_after, reason,
  idempotency_key, actor_type, actor_id, created_at)`
- `map_attempts`, `battle_sessions`, `battle_reports`, `reward_grants`,
  `reward_items`, `idempotency_keys`
- `shop_goods`, `shop_purchases`, `topup_orders`, `topup_reward_packages`,
  `withdrawal_requests`, `refunds`

### Social, tasks and live operations

- `friend_requests`, `friendships`, `friend_gifts`, `friendship_progress`
- `task_definitions`, `task_progress`, `task_claims`
- `activity_definitions`, `activity_progress`, `activity_claims`
- `sign_in_definitions`, `sign_in_claims`
- `notices`, `mail_messages`, `mail_recipients`, `gift_codes`,
  `gift_code_redemptions`, `outbox_events`

JSON is used only for extensible metadata, battle reports and adapter snapshots;
balances, ownership, claims and progression are columns/relations with unique
constraints. The SQLite compatibility store is never treated as the production
schema.

### Physical schema rules (M1 schema contract)

Table names above are logical groups. The implementation uses `*_definitions`
for content so `role_definitions` cannot be confused with `player_roles`.

| Group | Required columns / keys | Constraints and hot indexes |
| --- | --- | --- |
| game_servers | id, name, status, active_release_id, business_timezone | immutable ID; status enum maintenance/open/closed |
| accounts / sessions | id, normalized_login, password_scheme/hash; session token_hash, generation, expires_at, revoked_at | unique normalized_login/token_hash; index account_id/expires_at; no raw token storage |
| players | id BIGINT, account_id UUID, server_id, level/XP, version, power_milli, timestamps | unique(account_id,server_id); FK server/account; nonnegative XP/version; name policy separately validated |
| content_versions | id UUID, source_sha256, rules_sha256, status, created_by, published_at | published rows immutable; import rejects dangling item/skill/map refs |
| content definitions | content_version_id + kind_id, typed rules | composite PK; every gameplay session pins one content version |
| player_roles | id, player_id, role_class_id, kind_id, star, level, XP, awake_level, version | FK player; unique(player_id,role_class_id); duplicate recruitment converts via recorded policy |
| role_equipments / role_skill_levels | player_role_id + slot / skill_id, item_def_id, level, version | FK role, unique slot; base/derived attrs are projections, not separately editable totals |
| inventory_items | id BIGINT, player_id, kind_id, stack_key, quantity, version, metadata | CHECK quantity>=0; unique(player_id,kind_id,stack_key) for fungible stacks; one row per unique equipment |
| wallets | player_id + currency, balance BIGINT, version | PK(player_id,currency); CHECK 0<=balance<=configured cap |
| ledger_transactions / wallet_ledger | tx_id, command_id, player_id, currency, delta, balance_after, reason, actor, created_at | unique command reason; debit/credit postings balance per currency against system issuance/sink accounts; reversal references original |
| command_receipts | player_id, command_id UUID, route, payload_hash, result_json, aggregate_version, status | PK(player_id,command_id); unknown/inflight not reported as success; committed in gameplay TX |
| inventory_ledger / reward_grants | command_id, source_type/source_id, recipient, item deltas, content version | unique(recipient,source_type,source_id); reconcile to item quantities; duplicate source cannot mint twice |
| battle_sessions / reports | id, player_id, map_id, seed, team_snapshot, content_version_id, deadline, status; report hash/log | at most one active PvE session/player; report immutable; settlement unique battle ID |
| map_progress / daily_counters | player_id/map_id/best_star; player_id/counter_key/business_date/count | stars monotonic; daily counters keyed by reset epoch; no mass reset required |
| tasks/signin/activity claims | player_id, definition_id, definition_version, business_date or event_instance_id, reward_id | unique claim key including period; progress event_id dedup; index claim status/player |
| friend_requests/friendships/gifts | canonical player pair; sender/receiver/date/status | CHECK sender!=receiver; unique pair/request; gifts unique(sender,receiver,business_date); lock lower player ID first |
| notices/mail | template/version, audience, start/end, status; recipient/player/claim/receipt | index active windows and recipient unread; target list frozen on send; reward source stable |
| topup_orders/provider_events | provider/order/external_id, account/player, amount_minor,currency,sku_version,status; event_id/payload_hash | unique(provider,external_id/event_id); verify amount/currency/owner; paid transition once |
| refunds/withdrawals | original_order_id, amount_minor, status, requester, approver, reason, external_reference | unique provider operation; approver!=requester; totals cannot exceed original credited amount |
| admin audit / approvals | actor/session, command_id, action, target, reason, before/after redacted, approved_by, timestamp | append-only DB role; no arbitrary SQL/raw JSON editor; index target/time/actor |
| outbox_events / worker_receipts | event_id, aggregate_id/version, event_type, body, retry_count, next_attempt | unique event_id/consumer; bounded backoff, poison queue, claim with row locks |

### Transaction order

Authenticate -> authorize -> validate schema/content -> begin TX -> claim durable
command receipt -> lock player(s) and wallets in stable order -> check expected
version, funds, limits and ownership -> compute outcome -> ledger + inventory +
progress + reward claims + outbox + saved response -> commit -> serialize/send.
On a crash before commit no charge/reward survives; after commit retry returns
the same result. Outbox delivery is at least once; every consumer deduplicates.
Never publish an event or show a successful payment before commit.

### SQLite migration and cutover

Import from an offline backup opened read-only. Stage accounts, players and each
JSON subtree through a versioned mapper. Preserve unknown subtrees in an
encrypted migration archive plus anomaly report, not silent defaults. Record
old->new IDs, wallet opening-balance ledger entries, role/equipment/inventory
counts, map stars, counters, all existing claims and rejected records. Hash
source and manifest. Re-running the same import ID makes zero duplicates.

Legacy salted-SHA256 passwords retain a scheme marker only for login upgrade to
Argon2id; never invent plaintext or reset passwords silently. Revoke old RAM
sessions at cutover and require login. Require zero unexplained wallet/inventory
diffs in a restored rehearsal DB before the owner approves maintenance/cutover.
No dual-write between SQLite and PostgreSQL. After new writes, rollback means
version-compatible roll-forward or restore plus reconciled replay, not copying
an older SQLite file over live player progress.

## Invariants

1. A request may be retried safely with the same idempotency key and produces at
   most one state transition and one reward grant.
2. A player can mutate only their selected owned player; admin mutations require
   an authorized role and audit reason.
3. Currency balance equals the initial balance plus the sum of committed ledger
   deltas. No code writes a balance without its ledger entry.
4. Inventory quantity never becomes negative. A consumed stack and its reward
   grant commit in one transaction.
5. A map result is accepted only for a server-created battle session that has
   not expired or settled. Client star/outcome is an input signal, not proof.
6. A map unlock is derived from persisted progression/content rules, not from a
   client-provided map ID alone.
7. Power is recomputed from authoritative role/equipment/skill/friendship data
   at every relevant mutation and materialized for reads.
8. Content versions are immutable after publish. A rollback selects an older
   version; it does not rewrite historical reports.
9. Daily claims are keyed by `(player_id, definition_id, business_date)`.
10. Admin commands are append-only audit events with before/after summaries.

## Route delivery order

The route inventory is extracted from `client-recovered/src/project.js` and
tracked in `docs/protocol/vn-online-route-matrix.md`. A route moves through:

`STATIC_OBSERVED -> SCHEMA_FIXTURE -> SERVICE_IMPLEMENTED -> ADAPTER_TESTED ->
NATIVE_SMOKE_CONFIRMED`.

The initial must-have groups are bootstrap/auth/player, role/team, inventory,
map/battle/rewards, sign-in/tasks, shop/economy and friends. Unsupported routes
return a stable typed `NOT_IMPLEMENTED` error during development; they must not
return fake success.

## Battle and ability design

The battle engine consumes a versioned content snapshot and a validated team.
It executes turn/action ordering, target selection, hit/dodge/crit, buffs,
cooldowns, MP, death/revive and passive effects from imported skill tables.
The output contains `rulesVersion`, input team IDs, seed, action log, winner,
server timestamp and reward reference. A deterministic replay test must produce
the same report for the same version, seed and inputs. A client animation is
presentation only; the server report controls progression and rewards.

Start by mapping `battle.action*`, `fightSkillData`, `buffData`, targeting and RNG
call order; parity cannot be achieved by multiplying attack by seconds. Port
the smallest real action engine with a headless server interface; never execute
the full recovered bundle on the host. Manual abilities need sequenced input
events, ownership/MP/cooldown validation and logical timestamps. Extend the
versioned client adapter to send these commands; the old `endSmap(star,teamIndexs)`
alone cannot prove a manual battle. Persist input/report and settle the
authoritative result. No production PvE rewards until this bridge passes replay
fixtures and native animation/result comparison.

Pending/active/settled/expired/cancelled transitions are explicit. One active
battle per player, no mutation of its team snapshot, bounded duration/action
count, no loot resampling on retries. Disconnect retains a bounded resumable
session. AP debit and any refund policy are ledgered, approved content rules.
Sweep uses server eligibility (three stars, remaining attempts, tickets/gems)
and the same reward engine, not N forged `endSmap` calls.

## Admin API, roles and financial state

Admin uses `/admin/v1` on a separate internal host, not `logic.gmHandler` on the
game socket. GET list endpoints use cursor pagination (default 25, max 100),
stable sort, allowlisted filters and PII-minimized projections. Commands require
`Idempotency-Key`, `expectedVersion`, `reason`, and CSRF token for cookie auth.
401 unauthenticated; 403 insufficient role; 404 missing resource; 409 stale
version/reused-key mismatch; 422 invalid command; 429 rate limited. The `error`
envelope above is used consistently; player errors are translated at adapter.

| API surface | Commands / reads | Permission |
| --- | --- | --- |
| `/sessions`, `/me` | admin login/MFA, logout, revoke, current scopes | authenticated admin |
| `/users`, `/players`, `/players/{id}/timeline` | search/read profile, ledger and support notes | support-read |
| `/users/{id}/bans`, `/users/{id}/session-revocations` | ban/unban and revoke sessions | moderator |
| `/players/{id}/adjustment-requests` | request item/currency correction, immutable preview | support-write |
| `/adjustment-requests/{id}/approvals` | approve bounded correction; creator cannot approve | economy-approver |
| `/content-releases`, `/content-releases/{id}/publications` | validate draft/diff, publish/select prior version | game-designer + publisher |
| `/notices`, `/mail-campaigns`, `/mail-campaigns/{id}/dispatches` | draft/preview/schedule/cancel unsent; sent mail immutable | liveops |
| `/events`, `/events/{id}/activations`, `/events/{id}/claims` | definitions/windows, activate/deactivate, claim audit | liveops + publisher |
| `/gift-codes`, `/topup-gift-packages`, `/topup-gift-packages/{id}/publications` | versioned rewards/limits, qualification, redemption reports | liveops + economy-approver |
| `/topups`, `/topups/{id}/reconciliations`, `/refunds` | order evidence, reconciliation and refund request | finance-reviewer |
| `/withdrawals`, `/withdrawals/{id}/approvals` | review/hold/reject requests, sandbox-only payout | finance-approver |
| `/audit-logs`, `/health`, `/backups` | read redacted audit, operational and restore status | auditor / operator |

IDs for users/accounts here are UUIDs; player IDs are decimal strings. Request
DTOs allow only documented fields. Adjustment requests contain
`playerId, expectedVersion, deltas[{assetType, assetId, delta}], reason,
ticketReference`; preview returns `requestId, status, before, after, policyFlags`.
Approval returns `commandId, status, aggregateVersion, ledgerTransactionId`.
No client-supplied `approvedBy` or `actorId` is accepted. Access checks include
server/tenant scope, not only a global role name. Money/high-value or bulk
commands always need two distinct actors; small support grants have configured
daily caps. Super-admin bootstrap is one-time, audited and not a public endpoint.

The admin UI includes loading/empty/failure/conflict/retry states, read-only
ledger views, destructive confirmation with target/count, filters and a preview
before publish/send. Rich notice/event content is sanitized on input and output;
no arbitrary HTML/JS execution. Audit trail cannot be edited by support staff.

### Top-up and withdrawal lifecycle

Order: `CREATED -> PENDING -> VERIFIED_PAID -> CREDITED`; pending may become
`FAILED/EXPIRED`. Verified amount/currency/SKU/account/provider reference must
match the order. Provider callbacks are authenticated and deduplicated; browser
redirect/screenshot/manual client success is not proof. In one TX, VERIFIED_PAID
creates the currency ledger, order credit marker and top-up-gift qualification.
Retries never credit twice. Provider events may arrive reordered; status only
advances along allowed transitions. Reconciliation compares provider records to
ledger/order totals; disputed orders are held.

Refund: `REQUESTED -> REVIEWED -> APPROVED -> SENT -> CONFIRMED` or `REJECTED`;
ambiguous provider timeout stays `SENT/RECONCILING`, never resubmitted with a new
key. Compensating entries link to original credits; spent gems require an
explicit deficit/hold policy, not negative inventory or deleting history.

Withdrawal: `REQUESTED -> HELD -> APPROVED -> PAYOUT_PENDING -> PAID`, with
`REJECTED/CANCELLED/FAILED_RECONCILING` branches. Funds are reserved atomically and
released/consumed once. Game gems are **not** automatically cash redeemable.
Until owner approves what can be withdrawn, jurisdiction/provider/KYC/limits
and responsible operators, payout adapter remains disabled and all examples use
test money. Admin UI/API, recordkeeping and two-person approval can still be
implemented and tested in sandbox. This gate does not block core game delivery.

## Operations and security

- Development uses Docker Compose for PostgreSQL and Redis; production uses
  managed PostgreSQL with encrypted backups and Redis with no authoritative data.
- Secrets come from environment/secret storage, never source or logs.
- Passwords use a modern password hash; session tokens are stored hashed.
- Admin API requires MFA-ready RBAC, CSRF protection for browser sessions,
  request IDs, rate limits and audit logging.
- Metrics cover request latency/error rate, battle settlement failures, wallet
  imbalance, queue lag and database health. Alerts cover backup age and failed
  migrations.
- Backups are tested by restoring to an isolated database and running invariant
  checks. Production migrations are expand/contract and have a rollback plan.
- Lab MuMu traffic remains loopback/reverse-only with provider/payment egress
  blocked.

## Acceptance gates

### Gate A: core data

Fresh PostgreSQL migration, seed/import, rollback test and invariant checker
pass. A restart preserves account, team, inventory, wallet ledger and claims.

### Gate B: protocol

Every must-have route has a fixture test for success, validation, ownership,
retry and transaction failure. The adapter returns the exact client-consumed
fields. No route is marked verified from a unit test alone.

### Gate C: native client

On disposable `emulator-5554`, the current APK completes register/login,
home, team, map 10101, battle result, reward, role/equipment update, sign-in,
task claim, shop purchase and friend request. Capture screenshot, filtered
logcat and sanitized route trace for each flow.

### Gate D: admin

Admin can perform and audit a support grant, notice publish, event activation,
gift package claim review, top-up reconciliation and non-payable withdrawal
review. A revoked admin session cannot mutate state.

### Gate E: online readiness

Load tests meet documented SLOs, restore drill passes, no high-severity security
finding remains, and README/CHANGELOG/docs are synchronized in every commit.

Initial staging targets, not claims about current capacity: 500 concurrent
sessions, 100 ordinary commands/sec for 30 minutes on a recorded 4-vCPU/8-GB
baseline; p95 non-battle command latency <200 ms, application 5xx <0.1%, zero
duplicate grants or ledger imbalance. Also run 2-hour reconnect/idle soak and
20-way same-wallet/same-claim contention. Measure battle CPU/time separately;
set pool/timeout from those measurements before enabling load.

Backup objective: RPO <=15 minutes, RTO <=60 minutes, daily encrypted backups
with 7 daily + 4 weekly retention, continuous WAL archiving/PITR with archival
lag <=15 minutes, and a tested restore to a selected timestamp. Daily snapshots
alone do not meet the RPO. Treat these as launch
gates to benchmark and fund, not guarantees before restore/load tests.

## Decisions and trade-offs

- **PostgreSQL + Redis:** relational constraints and ledger correctness outweigh
  keeping the current zero-dependency demo runner. Redis accelerates ephemeral
  work but never owns balances or progression.
- **Modular monolith first:** one deployable service with strict modules reduces
  online consistency risk. Split workers/admin later when measurements justify it.
- **Protocol adapter over rewrite:** preserves the native APK contract while
  allowing the core to evolve. It prevents route-specific hacks from becoming
  the data model.
- **Admin commands over direct edits:** slower for support but protects economy
  integrity and makes every intervention explainable and reversible.
