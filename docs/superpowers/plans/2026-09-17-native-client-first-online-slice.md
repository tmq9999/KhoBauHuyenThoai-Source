# Native-client-first online slice Implementation Plan

> Historical checkpoint queue. Continue from the
> [APK online backend delivery plan](2026-09-17-apk-online-backend-delivery.md).
> Old open checkboxes are not a current implementation inventory; settlement
> and staged battle hooks were included in checkpoint990d8dc.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the recovered APK's real form/Pomelo contracts to PostgreSQL and deliver a native-confirmed 10106-to-10107 vertical slice.

**Architecture:** A native adapter owns `/user/*`, gate and connector sessions; PostgreSQL owns accounts, players, content, battle reports and rewards. The APK remains the unchanged recovered client except reviewed transport/bootstrap patches required to carry the exact contract.

**Tech Stack:** Python 3.12, FastAPI/stdlib loopback HTTP and Pomelo framing, PostgreSQL/Alembic, recovered Cocos client.

**Spec:** `docs/superpowers/specs/2026-09-17-native-client-first-online-slice.md`

**Execution:** owner explicitly requested immediate implementation. Continue on
the existing dirty feature branch; preserve unrelated work and prior evidence.
Current Task1 work was dispatched as old-plan Task7 before this replacement;
reuse its implementation/report, do not redispatch the same work.

## Global Constraints

- Compatibility SQLite runner is not an acceptance target or fallback.
- `client-recovered/src/project.js` and original APK are immutable.
- PostgreSQL is the only mutable game source; all rewards use ledger/receipt/outbox.
- No client-reported star/damage/loot is authoritative.
- No public listener, provider/payment traffic, physical-phone install or broad test claim.
- Every milestone requires native evidence before status changes to `NATIVE_CONFIRMED`.

### Task 1: Native form and Pomelo gateway

Status2026-09-17: source implementation + scoped wire verification reviewed.
Independent review approved after fixing revoke-during-content-wait race and
native heartbeat initiation. Not NATIVE_CONFIRMED. Old task7 evidence retained
in its original SDD workspace. Native deployment waits for metadata + Task2.

**Files:** Create `server-online/src/kbht_server/adapters/native_auth.py`, `native_gateway.py`; modify `server-online/src/kbht_server/cli.py`; tests only focused native contract helpers in SDD workspace.

**Interfaces:** `POST /user/register`, `/user/login`, `/user/serverInfo`; gate `queryEntry`; connector `entry`; player `getPlayers/createPlayer/entry`.

- [x] Extract literal request/consumer fields; verify real HTTP/Pomelo ownership,
  revoke-during-wait and heartbeat through bounded wire probe. Test-first was
  overridden by owner's immediate-client-first direction; no broad suite run.
- [x] Implement native errors and durable session/server binding with no SQLite or fake snapshot.
- [x] Run syntax and isolated PostgreSQL ownership checks; no compatibility runner.
- [x] Start `serve-native` with pinned metadata and restricted native role; real
  APK form auth/gate/connector/create/home observed2026-09-17 (opening release only).

Concrete verification once implemented:

```powershell
& './server-online/.venv/Scripts/python.exe' -I -m kbht_server.cli serve-native --help
& './server-online/.venv/Scripts/python.exe' -I -m compileall -q server-online/src/kbht_server/adapters
```

Wire probe must register via form, authenticate with returned token, handshake
using client sys, ACK, query gate, bind connector and get only owned players.
Replay/denial probes must not start the SQLite runner or mutate existing players.

### Task 2: PostgreSQL player snapshot/create/entry

2026-09-17 implementation checkpoint: normalized0014, source-bound definitions,
atomic creation, compressed native snapshot/entry, first rename and ledgered
recovery implemented. Scoped review approved after skill-prefix and missing
friendship-class validation fixes. NativeAvailability consumer guards reviewed.
Status SERVICE_TESTED/WIRE_TESTED only; actual activation policy/publication,
runtime grants and native APK first-home remain pending.

**Files:** Create `server-online/src/kbht_server/players/{creation,snapshots,stats}.py`,
`server-online/src/kbht_server/db/alembic/versions/0014_native_players.py` and
`docs/protocol/vn-native-player-snapshot.md`; modify `adapters/native_gateway.py`.
Check migration HEAD before assigning0014; use the next unused additive revision.

**Interfaces:** Full `connector.playerHandler.getPlayers/createPlayer/entry` DTOs matching direct client reads; player ownership/session/version/content pin.

- [x] Derive first-home direct reads from `project.js` consumers before writing DTO fields.
- [x] Implement persisted player creation with ledger/opening state and create-once replay; release activation remains gated, no live test grant.
- [x] Reconnect/revoke/store-reopen checks; required unresolved initialization is explicit policy, not a guessed default.
- [x] Native gate: APK registration/login/server/player flow reaches home with
  integer1059power; first rename and relog persist, no duplicate opening grant.
  Evidence docs/release/2026-09-17-native-postgres-opening.md; not battle acceptance.

First-home blocking reads already identified in original source:
`homeScene.genData:26158` dereferences the first two shopItems before level gating;
`activityPanel:2101-2122` dereferences four card catalog records even with an empty
activity map. Empty arrays alone are unsafe. Implement real source-backed shop
content, or a narrowly pinned client unavailable-control guard for genuinely
unsupported paid catalogs; never manufacture zero-price products. A guard keeps
original scenes/components and must not hide failures of supported game routes.
These guards belong in `client-recovered/patches/native-availability.js` and the
existing staged builder, never the pinned source.

Full source-cited field map is now
`docs/protocol/vn-native-player-snapshot.md`. Include two transport UI guards in
that staged patch: empty/maintenance server list must not dereference row0, and
socket connector callback53987 must not set isConnected after code500. These
guards cannot substitute for player/battle implementation.

Concrete implementation boundary:

```python
# Authenticated identity from connector, never account_id in client payload.
def create_player(account_id, server_id, name):
    """Single transaction; lock account+release, create once, ledger starter assets."""
def player_snapshot(account_id, server_id, player_id):
    """Consistent projection from owned persisted records; native DTO only."""
```

Complete the mapping of constructor/home/guide/bag/team before implementation.
Required first observations: initial role100101 from source49498ff; funds50gem,
0coin,60AP,10skill; six initial equipment IDs from roleData; time fields numeric
millis plus matching Vietnam formatted time. Leave unsupported feature controls
explicitly unavailable; do not invent purchasable goods, task rewards or events.

### Task 3: Tutorial recruitment and published normal-map authoritative battle

**Files:** Create `server-online/src/kbht_server/battles/{maps,engine,settlement}.py`, content publication gate and focused native evidence.

First create `server-online/src/kbht_server/players/recruitment.py` for only the
source-backed guide coin/gem single-draw contracts. Source guide22243-22359
automatically enters point2Role after rename. Capture exact guaranteed starter
rule/once markers before implementation; subsequent genuine draws must not be
repeated tutorial gifts. Remaining ten-draw/paid rules stay in the later slice.

Also create `client-recovered/patches/battle-command.js`, stage it through the
existing builder, and document seed/action/settlement DTOs at
`docs/protocol/vn-native-battle-authority.md`. Add revisions only for battle
sessions/reports/actions/map progress/claims required by this path.

**Interfaces:** `beginSmap`, sequenced server battle/report, settlement response consumed by `endSmap`; content release ID and reward source.

- [ ] Resolve combat duplicate blockers or explicitly keep the first native slice blocked; do not last-win silently.
- [x] Persist tutorial single recruitment via append-only role claims/receipt/outbox; verify
  original guide proceeds without pregranting Zoro/Nami or skipping guide state.
  Actual native coin/gem screens and PGclaims confirmed2026-09-17; repeat/paid/ten
  are separate pending commands. See native-postgres-tutorial release report.
- [ ] Port only source-backed action/target/buff rules with deterministic seed/report; reject forged result/star.
  2026-09-17 partial:45allowlisted source modules and deterministic SMAP runner
  implemented; actual persisted-role computation supports no-input and bounded
  manual end-tick skills. No native bridge or settlement yet, checkbox stays open.
- [ ] Publish normal-map graph including 10107 with AP/attempt/unlock checks and ledger rewards.
- [ ] Native gate: real APK selects 10106, wins, selects 10107, sees reward and persists after relog.

Concrete authority boundary:

```python
def begin_smap(command):
    """Debit AP once; persist content/team/seed and return battle ID."""
def submit_action(battle_id, sequence, skill_id, target):
    """Validate ownership, logical order, cooldown and MP; persist accepted input."""
def settle_smap(command, battle_id):
    """Use persisted server report; atomically ledger rewards/progress/receipt."""
```

Never accept a caller-supplied winner/star as settlement proof. Freeze manual
inputs before settlement; repeated command returns the original committed DTO.
First native progression proof includes rejected forged result with unchanged
wallet/items and real victory/relog with exactly one reward source.

### Task 4: Native release and handoff

**Files:** `docs/release/`, README/CHANGELOG/progress.

- [ ] Build exact APK/manifest, install `-r` only on isolated MuMu after firewall/device checks.
- [ ] Capture sanitized traces/screenshots and classify each route `NATIVE_CONFIRMED` or `BLOCKED_NATIVE`.
- [ ] Stop only after evidence is saved; do not claim complete game from this slice.

## Self-review

Coverage is deliberately limited to the first native vertical slice. Friends,
equipment, shop, tasks, recruitment ten-draw and later chapters remain future
slices. Any missing full snapshot field blocks Task2 rather than being invented.

## Next slices after the first native gate

Keep the full game scope, not a perpetual first-map demo. Execute these in order
using the exact route/acceptance contracts in the retained2026-09-16 design:

| Slice | Production files | Native delivery criterion |
| --- | --- | --- |
| Economy/progression | economy/purchases.py,shop.py; players/equipment.py,skills.py | Beli first purchase + own equip LV1->LV2/max/all, costs/stats persist; required materials obtainable |
| Recruitment | players/recruitment.py | four pointHandler single/ten routes, persistent RNG/duplicates/retries, no repeated starter gift |
| Social/liveops | social/friends.py,mail.py; liveops/tasks.py,sign_in.py | two actual accounts, gift/claim once across reset/relog, event-derived task progress |
| Admin/events | admin/api.py,rbac.py,audit.py; admin-panel/ | real role-enforced operations affecting native player, immutable audit |
| Finance/other modes | payments/; source-backed arena/guild/boss modules | sandbox finance only until approval; each visible mode separately native-confirmed |
| Online readiness | tools/ops/release_manifest.py,backup.py,restore.py | matched APK/content/rules/schema, restore and security gates before public exposure |

These are continuation milestones, not completed implementation or permission
to expose a server. Expand each bounded route task against actual consumers when
its predecessor works; don't restart foundational tooling or replace this plan.
