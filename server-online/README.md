# KBHT Online Backend

## Current execution set (2026-09-17)

Use the [online backend spec](../docs/superpowers/specs/2026-09-17-apk-online-backend-delivery.md),
[20-task plan](../docs/superpowers/plans/2026-09-17-apk-online-backend-delivery.md)
and [runbook](../docs/superpowers/runbooks/2026-09-17-apk-online-backend-delivery.md).
No Lab/emulator/ADB or broad test loops are requested. Existing setup/testing
commands below are reference, not an instruction to run them on every task.
The baseline CLI still supports only test/development and loopback; production
profile/activation/operations commands in the new runbook are planned interfaces.

## Recovered battle computation

`battles.engine.RecoveredBattleEngine(artifact).simulate_trusted(input)` runs only
allowlisted hash-pinned recovered battle modules in a fresh bounded Node child.
It is an internal computation API, not a gameplay route. Input must come from
server-owned persisted roles/content, never caller-supplied stats or winner.
Generate the ignored artifact from the pinned client:

```powershell
python tools/apk-recovery/extract-battle-modules.py --output work/battle-engine/modules.json
```

The package includes its JS driver, but not a full recovered application. The
extractor refuses source drift, outputs outside work/, links or overwriting a
different artifact. Repeated identical extraction is allowed. Node is required;
missing runtime/content, tampered artifact, execution/output limits fail closed.

`content.battle_bundle.battle_bundle(source,map_ids,role_ids)` selects literal
map/mob/role/skill/buff/math dependency closure. Duplicate definitions fail by
default; optional `vn-data-api-observed-lookup-v1` resolves only the two exact
reviewed candidate pairs and retains both rows with provenance in the digest.
This reproduces client lookup, not historical server intent or drop semantics.

The runner preserves recovered50ms tick/action order and accepts nonzero seed
plus bounded ordered `{zone,tick,skillId}` manual inputs. Same-tick distinct
skills preserve input order; invalid ownership/readiness/duplicates/unused actions
reject. Ships/auto mode remain unsupported. No route, AP debit, loot grant, map
unlock or native battle parity is implied. See
[battle authority contract](../docs/protocol/vn-native-battle-authority.md).

## Recovered native protocol entry point

`serve-native` exposes the exact native form `/user/register`, `/user/login`,
`/user/serverInfo` and standard Pomelo gate/connector entry rather than requiring
the APK to call `/v1`. All identity/session/server selection uses PostgreSQL;
there is no compatibility-runner import or SQLite fallback.

```powershell
& './server-online/.venv/Scripts/python.exe' -I -m kbht_server.cli serve-native --environment test --host 127.0.0.1 --http-port 20003 --gate-port 20100 --connector-port 20101
```

Database configuration and explicit migration prerequisites below apply. This
command never automatically creates servers/content/players. Add `--manifest`
and `--manifest-sha256` together to serve the exact validated build metadata on
20001 with the auth/gate/connector lifecycle. The manifest must point only to
the fixed local metadata origin; no arbitrary asset file serving is enabled.
Native createPlayer/entry require matching published
`native_player_content` and an explicit opening policy; absent definitions fail
with code500. Full battle/economy gameplay remains separate from starter entry.
Native app errors use `{code:500,msg}` rather than JSON API error wrappers.
ServerInfo returns public OPEN/PUBLISHED server rows and no account lookup by
username; owned players are listed only on an authenticated connector.
An empty published server list is maintenance, not a fabricated server1.

Gate queryEntry uses uid only as a routing hint. Connector entry validates
token, serverId and matching oldServerId; later requests recheck token/status/
content. Host/ports are loopback and distinct. HTTP, gate and connector share
one CLI lifecycle with partial-start cleanup. See the active
[native-first runbook](../docs/superpowers/runbooks/2026-09-17-native-client-first-online-slice.md).

## Persisted native starter state

Revision0014 adds native profiles, role ownership, owned skills, equipped slots
and map-progress relations. Native snapshots are projections, not mutable player
JSON. Create serializes the absent-player case with the account lock, uses stable
JS-safe IDs above10000 and emits one opening reward/ledger/receipt transaction.
Repeated create selects the same player. Entry validates ownership, selected
server, release and durable session, then gzip/base64-encodes the native DTO.
First rename persists once; retrying the same name is harmless. Later paid rename
is denied until a durable client action envelope is implemented.

`content.native_players.prepare_native_player_content(connection, version,
source, source_sha, policy)` accepts only a matching DRAFT content version and
the pinned recovered source. It does not publish a release. Its required policy
includes rules/provenance, power formula argument, initial owned skill levels,
skill cap and opening-state choices which the client alone cannot prove. No
default policy or automatic publication is supplied. A fixture policy is not
owner approval or native gameplay acceptance.

`players.creation` records starter gem/AP/skill credits through shared reward
and wallet ledgers with role/equipment creation. `players.snapshots` reads the
normalized state consistently and calculates time/stat fields; elapsed AP/skill
recovery uses the source300000ms interval with ledgered bounded credits. Missing
unimplemented catalogs stay empty and need the NativeAvailability client guards,
not dummy priced products. Initial role/skills/growth provenance and pending
policy decisions are in [native player contract](../docs/protocol/vn-native-player-snapshot.md).
Dedicated runtime-role grants for these new relations are still a deployment
prerequisite; do not expose a gateway using database-owner credentials.

`db.native_permissions` provisions a separate native runtime role without
changing the gameplay-only grants. It can authenticate/create/project/rename and
write append-only command/reward state, but cannot modify published definitions,
change ownership or perform persistent DDL. PostgreSQL default TEMP remains an
explicit local limitation. `native_setup` previews by default and applies only
with --apply, exact pinned opening policy, existing0014 schema and an unused or
exactly matching server identity. Private credential files are exclusive and
checked for owner/ACL/links before creation/reuse; retry never rotates passwords.

Tutorial recruitment extension0015 reads exact deterministic source first-drop
rows and stores new role claim+receipt+outbox atomically. `coin` then `gem` first
claims are free once; later empty-payload calls and ten-draw/paid routes are denied.
Lost replies require reconnect to resync roles, not repeated starter gifts.
`content.native_tutorial.prepare_tutorial_release` creates a new DRAFT, while
`activate_tutorial_release` explicitly migrates only compatible opening profiles
with a stopped listener. Original published content and historical receipts stay
unchanged. Runtime requires explicit `grant_native_tutorial_access` after0015.
These functions never run automatically on listener start or a player request.

## Authored bootstrap boundary

The opt-in account/bootstrap contract lives in
[online bootstrap](../docs/protocol/vn-online-bootstrap.md). It is separate from
the recovered native client's `/user/*` HTTP interface and gate/player entry.
New passwords use Argon2id; verified scrypt credentials can be upgraded without
resetting them. Additive revision `0013_account_status` introduces ACTIVE/LOCKED
accounts. Apply it through the existing explicit migration workflow before
running updated auth services; starting a listener never migrates automatically.

Do not use the gameplay runtime role to read password hashes. Auth runtime
credential provisioning remains separate, and the owner/migration credential is
only suitable for isolated lab tests. An inventory bootstrap cannot create a
playable player; account creation leaves player/item state untouched.

After explicit lab migration and database configuration:

```powershell
& '.\server-online\.venv\Scripts\python.exe' -I -m kbht_server.cli serve-bootstrap --environment test --host 127.0.0.1 --port 21003 --inventory-url ws://127.0.0.1:21002/inventory
```

Run `serve-inventory` separately for the selected WebSocket endpoint. Bootstrap
does not start it or populate it. `POST /v1/accounts` accepts `{login,password}`;
`POST /v1/sessions` returns a bearer token; `DELETE /v1/sessions/current` revokes
it. Authenticated `GET /v1/players?limit=25&after=0` lists only owned players.
`POST /v1/inventory/bootstrap` accepts `{playerId,serverId}` and returns the
current published release's hello, inventory URL and bag-only snapshot. Missing
ownership/content is denied; no test inventory is created by these endpoints.

No browser Origin requests, cookies or access logs. JSON bodies are limited to
4096 bytes with a5-second total read deadline; duplicate keys/nonfinite constants
are rejected. Errors omit validation input, password/token and SQL. All replies
are no-store. Auth hashing is limited to two concurrent requests and120 attempts
per60-second process-local window. These are lab limits, not a production
distributed rate limiter or HTTPS deployment. `serve` remains unchanged.

## Loopback inventory WebSocket transport

Run only after configuring the lab database and an appropriate pre-existing
account/player/session/content release. The listener never creates them:

```powershell
& '.\server-online\.venv\Scripts\python.exe' -I -m kbht_server.cli serve-inventory --environment test --host 127.0.0.1 --port 21002
```

Database configuration is the same as other CLI commands below. Use a dedicated
runtime role in a deployed process; migration-owner credentials are test-only.
This command is opt-in, distinct from `serve`, binds only127.0.0.1/::1, and accepts
binary WebSocket connections on `/inventory`. It is not internet-ready or a full
native gate/connector/bootstrap replacement.

The package-local Pomelo codec comes from the recovered compatibility codec;
no SQLite runner is imported. Handshake/ACK precedes DATA. The handshake user
contains token plus the bounded inventory hello; credentials never belong in
the URL. Requests retain durable command IDs independently of Pomelo request IDs.
`connector.inventoryHandler.resync` with empty payload returns replacement-bag
state; useItem carries the complete negotiated command envelope.

Resource limits:32 clients/32 admitted DB operations,64KiB input WebSocket
frames,16KiB HTTP headers,1MiB replies,10s read timeout. No route compression,
protobuf, WebSocket fragmentation or extensions. Header/frame/JSON validation
fails closed; unexpected errors do not expose SQL/token/tracebacks. Admitted DB
work drains on shutdown so disconnect does not mean rollback or safe reroll.

The listener does not provide account login, box acquisition or a full player
snapshot. Existing `serve` defaults remain unchanged. No client install or native
gameplay acceptance is implied by starting this transport.

## Opt-in native inventory adapter

`adapters.inventory_connection.InventoryConnection(engine)` wraps the adapter
with per-transport-connection state. `negotiate(token, hello)` authenticates and
selects a player/release; `execute(envelope)` checks token and pinned scope before
dispatch; `resync()` returns a fresh replacement bag; `close()` clears the binding.
Allocate one object per connection and always close on disconnect. Do not share
one negotiated object between unrelated clients.

Hello fields are exactly `protocolVersion:1`, `capabilities:["native-inventory-v1"]`,
`playerId`, `serverId`, `contentVersionId`. Failed negotiation clears any prior
identity. Responses advertise only useItem, `fullPlayerSnapshot:false` and
`snapshotMode:"replace-bag"`; they contain no token. Session expiry/revoke/rotation
is rechecked before each operation and after collecting snapshots. An operation
admitted before a concurrent revocation may finish; this is not atomic session
cancellation. Tokens remain private in process memory until close, not logged or
stored as plaintext in PostgreSQL.

Reconnect must negotiate again and retry the exact original envelope if its
response was lost. Do not rewrite command_id or expected_version. A new stale
command returns CONFLICT; fetch a replacement bag to recover state. This class
does not implement the client-side response ordering/queue, full player fields,
Pomelo framing or a network listener. Existing default server exposure is unchanged.

`adapters.native_inventory.NativeInventoryAdapter(engine)` exposes
`execute(authenticated_account_id, envelope, capability="native-inventory-v1")`
and `snapshot(account_id, player_id, server_id, content_version_id,
capability="native-inventory-v1")`. The caller must authenticate and negotiate;
the capability string itself grants no identity or access.

Execute accepts only `logic.playerHandler.useItem` within the existing durable
command envelope. Payload is `{bagIndex: "10001", itemCount: 1}`. Fresh online
bag keys are canonical strings of immutable PostgreSQL inventory IDs. There is
no implicit migration from old SQLite IDs. The fixed-box service enforces owner,
content/version and quantity rules; translated native bag deltas/rewards are
saved in the same receipt transaction and returned unchanged on replay.

Snapshot is a consistent bag-only view with aggregate/content versions, limited
to staged fixed-box/fragment kinds. It fails closed for unsupported metadata or
mixed content. Reconnect code must replace the bag, not merge a full snapshot
into stale state. This is not a full player bootstrap or Pomelo listener; no
default route is enabled. Native command queue/version-gap handling and APK
acceptance remain required.

## Fixed material-box service

Migration `0012_fixed_boxes` adds versioned `fixed_box_definitions` and
`fixed_box_rewards`, linked to existing item definitions. A controlled content
build may call `stage_fixed_box(connection, content_version_id, kind_id, source,
source_sha256)` in its own transaction. The target must remain DRAFT, match the
verified source hash and already contain every item definition with an explicit
stack policy. This does not create limits from APK `maxNum=-1` or publish content.
Only fixed fragment-only descriptors are supported; random/role/currency boxes
are rejected. Restaging checks raw provenance and exact normalized reward rows.

Register `economy.boxes.use_fixed_box` with `CommandExecutor` under the versioned
core route `inventory.useFixedBox` when ready. Payload is exactly
`{"inventory_id": 10001, "quantity": 1}`; kind/rewards/account identity cannot
be supplied in it. IDs here are PostgreSQL inventory IDs, **not native bagIndex**.
The handler validates ownership/content and caps a batch at100 boxes. It consumes
only the selected stack and grants all recipe items through the existing reward
service in one transaction with ledger, receipt and outbox.

The result contains consumed identity/count, selected-stack remaining quantity,
reward lines and affected-kind inventory records keyed by record ID. Zero rows
become null tombstones. This is a core DTO, not the native `_temp`/bag envelope.
Retries return the saved result; different input for one command ID conflicts.
Failure in any reward insert rolls back the consumption too. Runtime roles get
SELECT only on box definitions/rewards, no content edits.

Default `serve` does not register this route. Test HTTP apps explicitly enable it
with durable session authentication; that does not prove Pomelo/native parity.
Tests fund opening boxes through test-only ledger helpers. Real box acquisition,
combined content publication, stack policy and APK smoke are still required.

Durability coverage additionally exits a disposable child process before/after
commit, then retries through a fresh connection. The child is guarded to a
generated schema in `kbht_test`; this is not a production crash or restore drill.

## Material acquisition audit

`audit-acquisition --environment test --source client-recovered/src/project.js
--source-sha256 <verified-sha256>` uses the CLI/password-file setup below. It
validates379 drop rows and19 box descriptors, then reports static candidates
for78 equipment materials. W weights and R rates remain separate;177 zero-count
rows remain unresolved. No RNG or reward allocation is performed.

Source+report is stored in the existing immutable archive table under
`material-acquisition-v1`, without a new migration. Output includes archive
identity/digest, candidates, zero-count row count and `publishable=false`.
Repeated/concurrent calls verify and reuse the snapshot. Exit0 means storage
succeeded; `STATIC_CANDIDATES_ONLY` never means playable acquisition.

For49902, box321 contains6 units and five direct drop rows mention positive
quantities, but no repeatable normal map previews it. Box acquisition, class
invocation, selection semantics and native gameplay remain required.

## Equipment-only content drafts

After migration `0011_equipment_content`, `prepare-equipment --environment test
--source client-recovered/src/project.js --source-sha256 <verified-sha256>` creates
a separate versioned DRAFT with 120 equipment definitions and 342 ingredient
rows from the pinned source. Use the same Python CLI/password-file configuration
as the dependency importer below. This is not a combined playable release.

`content/equipment.py` checks IDs, entity types, finite numeric effects, recipe
shape/counts and cycles in evolution and ingredient graphs. `equipment_store.py`
stores raw snapshot, entity references, definitions and costs atomically; repeat
preparation compares all saved rows. Six terminal `evolutionItemId=0` values
become null pointers only in the projection. Source remains unchanged. Published
rows are guarded; no importer publishes or activates them.

Evolution cost belongs to the **target** recipe: going30101 ->30102 requires
40102,42102,49902 at one each. The importer does not invent stack limits from
`maxNum=-1`, populate runtime inventory, or prove materials are obtainable.

## Dependency evidence import

Migration `0010_dependency_archives` adds an append-only evidence store separate
from published definitions. After migrating the selected lab database:

```powershell
$env:KBHT_DB_PASSWORD_FILE = (Resolve-Path 'work/m1-env/secrets/postgres-superuser.txt').Path
& '.\server-online\.venv\Scripts\python.exe' -I -m kbht_server.cli import-dependencies --environment test --source client-recovered/src/project.js --source-sha256 9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818
Remove-Item Env:KBHT_DB_PASSWORD_FILE
```

The command returns archive ID/digest, counts, `reference_status`, issues and
`publishable=false`. Exit0 means evidence was stored, **not** content approval.
Same source/format retries compare the full stored bundle; concurrent imports
deduplicate. Different audit semantics require a new format version. No game
server, content version or player state is changed. The CLI roundtrip is tested
against generated isolated PostgreSQL schemas; do not use a live service DSN.

`content/dependencies.py` traverses normal-map mob/skill/buff references and
equipment/consumable entity references. `content/archive.py` stores original
ordered cells and the audit together. Conflicting IDs remain explicit blockers.
The archive is not a normalized battle ruleset; drop interpretation, recipe
cycles, effect semantics and native acceptance are pending.

`prepare-content --environment test --import-id <UUID>` prepares a DRAFT from
an existing content import. Migration `0009_normal_maps` adds immutable chapter
source archives plus `normal_map_definitions` and `normal_map_waves`, scoped by
content version. Preparation checks chapter references, numeric fields and
unique ranks, then stores ordered stages/waves in the same transaction as the
version. Replay compares complete projections and rejects altered, missing or
extra rows. Its versioned digest covers both source tables, not a validated
battle ruleset. Old smap-only imports require repeating `import-content` with
the same verified source to backfill chapters; old drafts are not overwritten.
`publish_source` rejects publication pending the gameplay validation gate;
no game-server status or active version is modified by preparation.

The raw archive retains all 1,623 stage rows and 69 chapter rows. Chapter
`type=1` selects 376 stages across 27 chapters, with 3,722 mob-wave references.
The strict source parser only permits missing trailing cells when explicitly
requested for a sparse table; it preserves absent keys rather than inventing
values. Mob and skill definitions and reward semantics are not validated by
the map projection. Published map/wave rows reject mutation.

`adapters.commands.CommandAdapter(executor, routes)` accepts a trusted account
UUID and a negotiated command envelope (command_id, player_id, server_id, route,
expected_version, content_version_id, payload). Routes default to denied.
Identity must be supplied by a separate authentication layer, never by the
request body. `adapters.http.create_app` exposes `/health` and `/v1/command`;
the loopback `serve` CLI resolves bearer tokens with `SessionService.resolve`.
It registers no gameplay handlers by default. The separate `serve-bootstrap`
listener exposes account/session endpoints; there is no full Pomelo bootstrap or
complete player snapshot adapter. No online-native cutover is implied. Public exposure
remains blocked on M2 authentication/security and runtime-role provisioning.

Python package `kbht_server` exposes a PostgreSQL command executor, ledger,
transactional outbox consumer and database CLI. The native HTTP/Pomelo lab
entry point is documented separately in [server-compatible](../server-compatible/README.md).
The complete service architecture is defined in the
[online-server specification](../docs/superpowers/specs/2026-09-16-online-game-server-design.md).

## Package layout

| Path | Interface / responsibility |
| --- | --- |
| `src/kbht_server/contracts.py` | `GameCommand`, `CommandResult`, `DomainFailure` |
| `src/kbht_server/db/session.py` | Explicit loopback database configuration and connection pool |
| `src/kbht_server/db/uow.py` | `CommandExecutor.execute`, `UnitOfWork.adjust_wallet`, `UnitOfWork.emit` |
| `src/kbht_server/db/schema.py` | SQLAlchemy table metadata |
| `src/kbht_server/db/permissions.py` | Dedicated unprivileged runtime-role grants |
| `src/kbht_server/db/repositories.py` | Owned inventory stacks, adds/consumption and item ledger |
| `src/kbht_server/economy/rewards.py` | Idempotent item/currency grants with source provenance |
| `src/kbht_server/db/alembic/versions/` | Frozen SQL revisions packaged with the backend |
| `src/kbht_server/db/migrations.py` | Transactional migration and read-only invariant checks |
| `src/kbht_server/workers/outbox.py` | `OutboxConsumer.consume` and typed `OutboxEvent` |
| `src/kbht_server/workers/poller.py` | Leased discovery, fencing, retry/backoff and dead-letter state |
| `src/kbht_server/cli.py` | `migrate`, `check-invariants` |
| `tests/pg_lab.py` | Two-account PostgreSQL fixture, opening ledger and test-only projection |

## Install

Run commands from the repository root using Windows x64, Python 3.12 and
PowerShell. `requirements.lock` pins dependencies and package hashes for this
platform. `redis` in the dependency list is a Python client, not a Redis server.

```powershell
python -m venv server-online/.venv
& '.\server-online\.venv\Scripts\python.exe' -I -m pip install --require-hashes -r server-online/requirements.lock
& '.\server-online\.venv\Scripts\python.exe' -I -m pip install --no-deps --editable ./server-online
```

## Database configuration

| Environment variable | Meaning |
| --- | --- |
| `KBHT_DATABASE_URL` | Development SQLAlchemy DSN, `postgresql+psycopg`, database exactly `kbht_dev` |
| `KBHT_TEST_DATABASE_URL` | Test DSN, database exactly `kbht_test` |
| `KBHT_DB_PASSWORD_FILE` | ASCII password file used when the selected DSN is absent |
| `KBHT_DB_USER` | User in password-file mode, default `kbht_admin` |
| `KBHT_DB_PORT` | Port in password-file mode, default `25432` |

Password-file mode uses `127.0.0.1`; DSN mode accepts loopback hosts only and
rejects query overrides. Test configuration never falls back to the development
DSN. The CLI reads process environment variables, not dotenv automatically;
[.env.example](.env.example) is a reference. Connections set UTC, a 5-second
connect timeout, a 15-second statement timeout and a 10-second lock timeout.

Compose uses `KBHT_POSTGRES_PASSWORD_FILE` and `KBHT_REDIS_ACL_FILE` explicitly;
the repository includes [redis.acl.example](redis.acl.example) with the default
Redis user disabled. Replace it with an ignored ACL file containing a dedicated
application user before starting Redis. Never use the bootstrap PostgreSQL
password as an application password in a shared environment.

For the workspace portable PostgreSQL 18.6 installation, configure paths once:

```powershell
$pg = (Resolve-Path 'work/m1-env/postgresql-18.6/pgsql').Path
$data = (Resolve-Path 'work/m1-env/pgdata').Path
```

Start and inspect the cluster:

```powershell
& "$pg/bin/pg_ctl.exe" -D $data -l 'work/m1-env/postgres.log' -o '-h 127.0.0.1 -p 25432' -w start
& "$pg/bin/pg_ctl.exe" -D $data status
& "$pg/bin/pg_isready.exe" -h 127.0.0.1 -p 25432
```

Stop it separately after stopping database clients:

```powershell
& "$pg/bin/pg_ctl.exe" -D $data stop -m fast
```

This portable layout does not register a Windows service or automatic startup.
Run database commands as the Windows owner of its data and credential files.
Installation provenance and workspace-specific artifacts are recorded in the
[execution log](../docs/agent-runs/online-server-progress.md).

## Migration and tests

```powershell
$env:KBHT_DB_PASSWORD_FILE = (Resolve-Path 'work/m1-env/secrets/postgres-superuser.txt').Path
& '.\server-online\.venv\Scripts\python.exe' -I -m kbht_server.cli migrate --environment development
& '.\server-online\.venv\Scripts\python.exe' -I -m kbht_server.cli check-invariants --environment development
& '.\server-online\.venv\Scripts\python.exe' -I -m pytest -q server-online/tests -p no:cacheprovider
Remove-Item Env:KBHT_DB_PASSWORD_FILE
```

`migrate` creates/selects `kbht_core` and runs Alembic revisions in a transaction.
An unversioned populated schema is rejected rather than stamped. The CLI does
not use tables in `public`. Tests require real PostgreSQL `kbht_test` and create,
migrate and drop only their own `kbht_t_<uuid>` schema. Missing DB configuration
fails test setup rather than silently skipping integration tests.

For a service process, provision a dedicated role named `kbht_runtime` or
`kbht_test_runtime_<32-hex>`, with `NOINHERIT`, no memberships, superuser,
database/schema/table ownership or pre-existing excessive grants.
Call `grant_runtime_access(connection, role)`
from a controlled provisioning process after migrations. It grants only the
SELECT/INSERT and projection-column UPDATE privileges needed by commands;
ledger, receipt, outbox, content and server identities stay trigger-protected.
The bootstrap `kbht_admin` role is an owner/migration role and must not be used
by a public gateway. Runtime-role provisioning is not an automatic CLI side effect.
Login/password provisioning is separate; tests use disposable `NOLOGIN` roles
and `SET ROLE` to exercise the ACL rather than creating persistent logins.
These permissions limit what the internal service can change, not which player's
row it can address; account/player authorization is enforced by `CommandExecutor`.

`check-invariants` uses a repeatable-read, read-only transaction and reports:

- `wallet_mismatches`: wallet totals differ from ledger deltas or exceed bounds.
- `unbalanced_transactions`: missing postings or nonzero net per currency.
- `posting_mismatches`: player postings differ from wallet ledger entries.
- `orphan_receipts`: receipt owner is missing or receipt version exceeds player version.
- `inventory_mismatches`: stack quantity/version differs from its ledger or content limit.
- `inventory_history_mismatches`: a historical quantity differs from the running delta sum.
- `reward_item_mismatches`: normalized reward quantities differ from linked item ledger entries.
- `reward_currency_mismatches`: reward currency lines differ from linked wallet postings.

## Inventory and rewards

Use `work.inventory` and `work.rewards` inside a registered `CommandExecutor`
handler, on its existing locked player transaction. These are domain APIs,
not public player/GM routes. Authorization, eligibility, price and loot selection
belong to the calling domain service; a player payload must not select its reward.

```python
def settle_verified_reward(work, verified_reward):
    return work.rewards.grant(
        source_type=verified_reward.source_type,
        source_id=verified_reward.source_id,
        items=verified_reward.item_quantities,
        currencies=verified_reward.currency_amounts,
    )
```

`items` is `dict[int, int]` of kind ID to positive quantity; `currencies` maps
currency name to positive integer units. Each item must exist in the command's
published `item_definitions` version. `grant` returns `grant_id`, item lines and
credited currency amounts (not current wallet balances). A retry with the same
recipient/source type/source UUID returns the saved grant. A changed reward or
content version for that key raises `CONFLICT`. No new loot/event is issued on
a source replay, even if the outer command ID is different.

`work.inventory.add(kind_id, quantity, reason=...)` fills existing stacks in ID
order then creates bounded stacks. `consume(kind_id, quantity, reason=...,
inventory_id=...)` debits only the selected owned record; omitting `inventory_id`
is the server-side aggregate-material operation across stacks. Supplying another
player's record returns `NOT_FOUND`. Counts reject booleans, fractional, zero,
negative and unsafe-integer values. Insufficient quantity raises
`INSUFFICIENT_FUNDS`, with the whole command rolled back.

Zero-quantity rows retain their IDs and ledger references. Client adapters derive
inventory tombstones from those rows. Definition `stack_limit=1` allocates separate
single-unit records; equipment attributes/equip rules are a separate domain layer.
Each add/consume is bounded to 1,000 stack writes and safe-integer totals. Inventory
from a different content version fails `CONTENT_UNAVAILABLE` until migrated.

`item_definitions` can be edited only while its content version is `DRAFT`.
Published content/provenance and item/reward ledgers reject mutation/deletion;
publication changes use a new version, not an edit or unpublish-in-place.
Additive revisions are `0003_inventory_rewards`, `0004_content_immutability`,
`0005_runtime_guards` and `0006_outbox_delivery`.
Handlers must propagate a failed domain operation so the executor rolls back
all wallet/item/grant/receipt/event writes, rather than committing partial work.

## Command and outbox contracts

`CommandExecutor(engine, handlers).execute(command)` locks the owned player,
checks the expected aggregate/content version and invokes the registered
handler with one `UnitOfWork`. Handler wallet adjustments, paired ledger
postings, emitted events, saved result and version increment commit together.
Exact command replay returns the persisted result. Same key with different
input raises `DomainFailure('CONFLICT', ...)`.

`OutboxConsumer(engine, consumer, handlers).consume(event_id)` accepts a UUID
for a persisted event. `handlers` maps event type to
`handler(connection, event: OutboxEvent)`. The `(consumer, event_id)` receipt
and projection update commit together. Concurrent retries wait for the same
receipt; success returns `True`, an already-processed event returns `False`.
Missing/unsupported events raise `NOT_FOUND`/`NOT_IMPLEMENTED`. Handler errors
roll back both receipt and projection, allowing a later retry.

Handlers use only the supplied connection and do not commit, open their own
transaction or perform external side effects. A database receipt cannot make
an HTTP request or payment callback exactly-once. Independent event handlers
must use row locks or atomic upserts for shared projections. The consumer is
an explicit-delivery API, not a polling/scheduling service.

`OutboxPoller` adds explicit delivery scheduling: `discover()` registers
supported event types, `claim()` creates a persisted lease, `perform()` fences
stale workers and runs the handler, and `poll_once()` returns `DONE`, `RETRY`,
`DEAD`, `LOST` or `IDLE`. Retry budget, lease token, next-attempt time and
last-error code are stored in `outbox_deliveries`. Backoff is bounded
exponentially. Receipt, projection and `DONE` state commit together; a direct
consumer and poller sharing an event cannot double-apply it. Terminal records,
retry budget, identity and deletion are database-guarded. `run(stop)` is a
caller-owned loop and performs no external side effects. Migration
`0006_outbox_delivery` is required.

`tests/pg_lab.py` seeds two accounts with opening ledger entries. The internal
purchase command and projection counter are test fixtures, not player routes,
shop prices or daily-task rules.

## Durability and privilege tests

The full suite requires a lab test DB owner with `CREATEROLE` for disposable
runtime-role fixtures, plus `pg_dump` and `pg_restore` of a compatible PostgreSQL
version. Set `KBHT_PG_BIN` to the client-tool directory, or put the tools on PATH.
On the workspace Windows lab the portable PostgreSQL directory is detected.

```powershell
$env:KBHT_DB_PASSWORD_FILE = (Resolve-Path 'work/m1-env/secrets/postgres-superuser.txt').Path
$env:KBHT_PG_BIN = (Resolve-Path 'work/m1-env/postgresql-18.6/pgsql/bin').Path
& '.\server-online\.venv\Scripts\python.exe' -I -m pytest -q server-online/tests/integration/test_durability.py server-online/tests/integration/test_runtime_role.py -p no:cacheprovider
Remove-Item Env:KBHT_DB_PASSWORD_FILE, Env:KBHT_PG_BIN
```

Crash tests exit a child Python process before/after commit, then retry the same
command. Restore tests dump only their generated `kbht_t_<uuid>` schema in
`kbht_test`, remove that schema, restore it in one transaction and compare rows,
replay, worker receipts and invariants. They never target `kbht_core` or the
SQLite game database. Runtime tests create and remove only their generated
`kbht_test_runtime_<uuid>` roles. Backups are synthetic test artifacts; this is
not a production PITR/RPO/RTO procedure.

## Compose model

`compose.yaml` models local dev/test PostgreSQL and Redis only. Images are pinned
by digest. PostgreSQL 18 stores data under `/var/lib/postgresql`, with separate
loopback ports `25433` (`kbht_dev`) and `25434` (`kbht_test`); Redis is loopback
`26379`, ACL-file authenticated and configured without AOF/RDB persistence.
Secrets are required through `KBHT_POSTGRES_PASSWORD_FILE` and
`KBHT_REDIS_ACL_FILE`; default passwords are not embedded. Validate without an
engine:

```powershell
$env:KBHT_POSTGRES_PASSWORD_FILE = (Resolve-Path 'work/m1-env/secrets/postgres-superuser.txt').Path
$env:KBHT_REDIS_ACL_FILE = (Resolve-Path 'server-online/redis.acl.example').Path
& '.\work\m1-env\download\docker-compose-v5.5.1.exe' -f compose.yaml config --format json
Remove-Item Env:KBHT_POSTGRES_PASSWORD_FILE, Env:KBHT_REDIS_ACL_FILE
```

The current machine has no Docker Engine. Compose syntax/interpolation is tested;
container health and Redis connectivity require a Docker-enabled host.
