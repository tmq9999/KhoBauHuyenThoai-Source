# KBHT Online Backend

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
Additive revisions are `0003_inventory_rewards` and `0004_content_immutability`.
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
