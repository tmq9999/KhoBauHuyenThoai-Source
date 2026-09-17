# Kho Báu Huyền Thoại APK Online Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Owner override: no Lab/emulator/ADB, no broad test loops or synthetic gameplay; implement product code directly and record unexecuted checks honestly.

**Goal:** Hoàn thiện backend online dùng đúng client APK, từ gameplay đến admin và vận hành, không làm lại nền tảng đã có.

**Architecture:** Giữ Python modular monolith, Pomelo native adapter, PostgreSQL ledger/receipt/outbox và engine combat allowlist. Client chỉ thêm patch transport/command trong stage; source phục hồi giữ nguyên.

**Tech Stack:** Dependency pins hiện có trong server-online; Python, PostgreSQL, SQLAlchemy/Alembic, JavaScript ES5 native patch; Node chạy logic combat chọn lọc. Không nâng phiên bản trong task gameplay.

**Spec:** [apk-online-backend-delivery](../specs/2026-09-17-apk-online-backend-delivery.md).
**Runbook:** [thực thi và vận hành](../runbooks/2026-09-17-apk-online-backend-delivery.md).
**Baseline:** `990d8dc`, đã push; đây là hàng đợi mới được owner yêu cầu, không xóa lịch sử.

## Global Constraints

- Không dựng/chạy Lab, emulator, ADB, smoke vòng lặp hoặc seed tài khoản/vật phẩm.
- PostgreSQL là nguồn trạng thái duy nhất; không quay về server-compatible.
- Source APK và project.js pinned bất biến; không full-bundle execution trên server.
- Không tin star/damage/price/loot client; không cấp no-item-drop fixture làm gameplay.
- Không broad suite/benchmark hoặc task chỉ tạo test count; giữ nguyên bằng chứng cũ.
- Mỗi commit giao hàng có README.md và CHANGELOG.md đúng trạng thái.
- Chưa được owner cho phép thì không publish dịch vụ, migrate DB thật, thao tác thiết bị hoặc gọi payment.
- Giữ native errors, durable retry, ownership, append-only ledger và content pins.

## A. Kiểm tra plan/spec/runbook cũ

1. Task1/2 đã có code và bằng chứng native opening; không redispatch xây mới.
2. Tutorial có native report; general recruitment vẫn thiếu, không gọi cùng một
   claim tutorial để xử lý request mua tiếp theo.
3. Task3 cũ nói chưa có settlement/hook là stale: commit baseline đã chứa cả hai.
4. Content combat có deliberate duplicate policy; blocker thực tế là loot rules,
   wider role support và activation cho player đã tiến triển, không phải viết lại engine.
5. `db/session.py`, `native_setup.py`, `native_permissions.py`,
   `content/native_battles.py`, CLI, metadata và gateway đang có local-only guards.
   “Đổi IP server” không đủ để chạy online.
6. Native inventory service có thể dùng lại nhưng chưa là route useItem đầy đủ
   trên native gateway; inventory-only listener không phải frontend game thứ hai.
7. Lab commands ở runbook cũ không còn được thực hiện. Bộ mới ghi rõ lệnh có sẵn
   và giao diện dự kiến, không giả vờ có production CLI.

## B. Bản đồ file và trách nhiệm

| Khu vực | Giữ/tái sử dụng | File mới chỉ khi cần |
| --- | --- | --- |
| Native transport | adapters/native_auth.py, native_gateway.py, pomelo_codec.py, pomelo_transport.py | adapters/native_commands.py, runtime/config.py |
| State/transaction | contracts.py, db/uow.py, db/schema.py, db/native_permissions.py | migration append sau0016; cập nhật schema cùng task |
| Content | content/source.py, importer.py, native_players.py, native_tutorial.py, native_battles.py | content/rewards.py, recruitment.py, release.py |
| Combat | battles/maps.py, engine.py, driver.cjs, settlement.py | battles/sweep.py; mode module theo inventory |
| Player/economy | players/creation.py, snapshots.py, stats.py, progression.py, recruitment.py; economy/rewards.py, boxes.py | players/equipment.py, skills.py, teams.py; economy/purchases.py, inventory.py, shop.py |
| Live features | workers/outbox.py, poller.py | liveops/tasks.py, sign_in.py, activities.py; social/friends.py, mail.py, gift_codes.py |
| Admin/ops | existing DB/command layer | admin/auth.py, rbac.py, api.py, audit.py; ops/release.py, backup.py, restore.py, health.py; deploy/* |
| APK | build-repacked.ps1, stage-client-patches.py, battle-command.js | patches/native-command.js, online-endpoints.js; tools/apk-recovery/prepare-online-endpoints.py |

Các đường dẫn Python trong bảng nằm dưới `server-online/src/kbht_server/`;
`deploy/` là root repository. Không tạo file rỗng cho toàn bộ bảng trước.

## C. Dependency và thứ tự

T01 contract ledger -> T02 command bridge -> T03 role/stat -> T04 loot ->
T05 battle -> T06 purchases -> T07 equipment -> T08 progression -> T09 recruit ->
T10 inventory/shop -> T11 tasks/sign-in -> T12 social -> T13 mail/events ->
T14 admin -> T15 finance records -> T16 remaining modes -> T17 production profile
-> T18 online APK -> T19 operations -> T20 release handoff.

Nếu T04/T09/T16 thiếu luật, ghi `BLOCKED_RULE` đúng route/rule rồi làm task
không phụ thuộc; không bỏ trắng loot hoặc bật giả success. T17/T19 có thể làm
khi gameplay chờ quyết định, nhưng không được deploy để bỏ qua các dependency.

## D. Hợp đồng chung cho mọi task ghi dữ liệu

Giữ interface đang có, không bịa thêm một executor:

```python
GameCommand(command_id, account_id, player_id, server_id, route,
            expected_version, content_version_id, payload)
CommandExecutor(engine, handlers).execute(command)
# Handler thực hiện bên trong transaction đã có:
# handler(work: UnitOfWork, payload: dict) -> dict
# Trả native delta vào receipt cùng transaction, không serialize state mới khi retry.
```

Mỗi task phải ghi contract `builder span -> domain fields -> consumer span`,
success delta, denied delta, stable reward source và receipt key. Khi thêm schema,
đọc migration HEAD thực tế và cấp revision tiếp theo, không đặt trước20 revision.
Các tình huống nghiệm thu dưới đây là tiêu chí sản phẩm, không phải lệnh chạy
test suite trong phiên thực thi. Nếu chưa owner xác nhận thì giữ `NOT_RUN`.

### Task T01: Đồng bộ contract/status từ source và implementation

**Files:** sửa `docs/protocol/vn-online-route-matrix.md`, `vn-core-consumers.json`;
tạo `docs/protocol/vn-online-delivery-ledger.md`.
**Consumes:** inventory230 route và callback source; baseline gateway.
**Produces:** ledger theo từng route với owner task, handler, state, blocker.

- [ ] Đối chiếu từng route CORE với nhánh dispatcher thực có, tách cột PostgreSQL và SQLite historical.
- [ ] Gắn auth/player scope, request keys, compressed/raw response, `_temp`, merge/tombstone consumer cho từng route cần triển khai.
- [ ] Ghi riêng dynamic routes chưa phân giải; không gọi230 là toàn bộ game đã hiểu.
- [ ] Ghi status battle là implementation có sẵn, loot chưa đủ, native acceptance chưa có; tutorial khác paid draw.
- [ ] Cập nhật README/CHANGELOG và commit `docs: reconcile native route delivery baseline`.

**Done:** không có route `IMPLEMENTED` chỉ vì xuất hiện trong JSON; mỗi route có
handler thực hoặc blocker và task đích. Không bắt đầu lại inventory tooling.

### Task T02: Durable command bridge cho gameplay native

**Files:** tạo `adapters/native_commands.py`, `client-recovered/patches/native-command.js`;
sửa native_gateway.py, contracts.py nếu cần, stage-client-patches.py, builder.
**Consumes:** authenticated NativeConnection, GameCommand, snapshot version.
**Produces:** capability `native-commands-v1`, staged queue và dispatcher domain.

- [ ] Định nghĩa envelope thương lượng chứa commandId/expectedVersion/contentVersionId/payload; strict legacy routes vẫn nhận body cũ cho đến khi client đã negotiate.
- [ ] Sinh ID một lần ở thao tác UI, lưu queue theo account/player/server/release; không lưu password/token trong queue; serial mutation theo player.
- [ ] Map authority từ connector, revalidate sau lock wait, lưu native response vào receipt; cùng ID khác payload conflict, lỗi thiếu tiền không trừ gì.
- [ ] Reconnect gửi lại đúng ID hoặc lấy receipt; delta chỉ apply theo version, gap thì snapshot; đổi account xóa binding chứ không replay nhầm người.
- [ ] Nối một route domain có sẵn theo allowlist, giữ battleId-specific protocol; ghi contract/README/CHANGELOG và commit.

**Nghiệm thu:** timeout sau commit không mua hai lần; hai callback đảo thứ tự
không giảm wallet/role version; old client không được thực hiện paid mutation mơ hồ.

### Task T03: Hoàn thiện role definition, stat và snapshot thống nhất

**Files:** sửa content/native_players.py, battle_bundle.py, players/stats.py,
snapshots.py, progression.py; tạo `docs/protocol/vn-role-progression.md`.
**Consumes:** role/equipment/skill/friendship tables của APK; opening policy.
**Produces:** một projection stat dùng cho UI, battle input và command delta.

- [ ] Map star/level/awake/passive/equipment/skill từ source; khoanh chính xác đoạn đang chỉ cho star1/ba starter role.
- [ ] Thêm content validator cho từng loại role được route mới cấp; missing class/skill/buff chặn release, không điền0 để chạy tiếp.
- [ ] Thực hiện công thức fixed-point và full role record; sum power trước floor; giữ policy mở đầu cho player cũ, không sửa raw source.
- [ ] Version hóa quan hệ đội hình/roster/battle stat; chỉ dùng owned role khi dựng team snapshot.
- [ ] Ghi rõ power argument chưa chứng minh ngoài opening nếu còn; cập nhật docs và commit.

**Nghiệm thu:** cùng equipment/skill/level cho cùng stat ở snapshot và combat;
home/team power là integer, không NaN; thiếu rule thì không cho upgrade tương ứng.

### Task T04: Loot thật và acquisition graph

**Files:** tạo content/rewards.py; sửa content/acquisition.py, native_battles.py,
economy/rewards.py; cập nhật vn-material-acquisition.md, vn-native-battle-authority.md.
**Consumes:** source drop rows, W/R/group/weight/count, normal maps, box recipes.
**Produces:** versioned reward rules và deterministic resolved grant được receipt lưu.

- [ ] Truy source cho specifyDropValues và count0; ghi selection, weight, quantity, first-clear/repeat, empty outcome tách biệt.
- [ ] Nếu APK không đủ, viết proposal luật mới với xác suất/quantity/reason và xin owner chọn; giữ route đó blocked, không lấy no-item-drops-v1 làm default.
- [ ] Persist RNG seed/outcome và reward source; validate item class/stack/cap; gọi grant_rewards trong cùng transaction settle/claim.
- [ ] Nối nguồn thực cho vật liệu49902 và mọi nguyên liệu upgrade mở UI; không grant bằng console/seed hoặc chỉ ghi “có trong bảng”.
- [ ] Xóa sự phụ thuộc gameplay vào policy fixture bằng policy implementation có provenance; commit kèm docs.

**Nghiệm thu:** người chơi kiếm vật liệu bằng route game; retry không roll lại;
map không đủ content không trừ AP; mọi balance/item delta truy về nguồn thưởng.

### Task T05: Khép kín native battle và map progression

**Files:** sửa battles/maps.py, settlement.py, engine.py, content/native_battles.py,
players/snapshots.py, battle-command.js, prepare-native-battle.py; tạo battles/sweep.py.
**Consumes:** T02/T03/T04, migration0016 và scoped fixes baseline.
**Produces:** begin/end/skip/resetSmapTimes/receiveBmapAward khi đủ contract.

- [ ] Giữ stale timer fencing, request/team/map copy, consumed tick và frozen submission; đối chiếu source battleMain và smap callbacks thay vì viết hook khác.
- [ ] Hoàn thiện artifact/release binding, timeout/disconnect/resume, manual MP/cooldown/queue và report mismatch; không tin client star.
- [ ] Nối real reward resolver, source AP/attempt/unlock, repeatability, role/player XP và recovery deadlines; grant một lần theo battle ID.
- [ ] Mở graph10106→10107→chapter2 với đủ content và nguồn nâng đội hình; nếu đội thua thì trả thua, không điều chỉnh kết quả để hoàn tất milestone.
- [ ] Sweep chỉ từ eligibility persisted; reset/chapter claim có counter/cost/unique source riêng; route thiếu rule vẫn unavailable.
- [ ] Thay activation-only-opening bằng compatibility plan cho player đã lên cấp/có inventory; old battle/receipt giữ pin cũ; commit docs.

**Nghiệm thu:** thắng thật -> reward/progress -> relog; star giả không thưởng;
win/nonrepeatable không được farm; retry/settle expired không tạo ledger dư.

### Task T06: Beli, AP và skill-point purchases

**Files:** tạo economy/purchases.py; sửa native_commands.py, snapshots.py;
migration cho daily counters nếu schema chưa đủ.
**Consumes:** buyCoin/buyActionPoint/buySkillPoint builder và VIP consumer.
**Produces:** ba route dùng server quote/cost/outcome, native delta đúng trường.

- [ ] Map VIP/reset/max-times/price rows; `vip.buyCoinTimes` luôn là integer0 trước lần đầu, không undefined.
- [ ] Giữ báo giá và outcome dưới command ID/release; debit gem, credit coin/AP/SP, counter, ledger, receipt/outbox cùng transaction.
- [ ] Trả `_temp.costGem/getCoin/ratio` và các trường consumer thực đọc, không dùng số screenshot làm RNG rule.
- [ ] Áp dụng giới hạn funds/cap/day/owner/expectedVersion; duplicate cùng ID là replay, thao tác lần2 là command mới.
- [ ] Cập nhật route ledger, README/CHANGELOG và commit.

**Nghiệm thu:** VIP0 hiện0/1 và lần đầu10gem theo source; thiếu gem không tăng
counter; retry không trả tiền hai lần; đổi ngày không làm mất receipt cũ.

### Task T07: Equipment level/max/all

**Files:** tạo players/equipment.py; sửa content/equipment.py, equipment_store.py,
players/stats.py, snapshots.py, native_commands.py; schema/migration liên quan.
**Consumes:** upgradeEquipment/upgradeEquipmentMax/upgradeAllEquipmentMax.
**Produces:** upgrade có cost ledger và full role consumer `eqptScene` nhận được.

- [ ] Map teamIndex/equipmentType sang owned slot, lấy cap từ role/player/source.
- [ ] Tính tổng từng bước level từ bảng giá, không nhân giá cuối; max chỉ đến mức có thể mua đúng native semantics.
- [ ] Debit coin + đổi equipment level + tính stat/power + event task + receipt nguyên tử.
- [ ] All-max khóa cùng player và ghi tất cả slot trong một transaction, không partial charge khi lỗi.
- [ ] Ghi source price evidence, docs và commit; không tạo vật liệu/coin để trình diễn.

**Nghiệm thu:** fixture source LV1→4 một slot360coin, sáu slot2160coin khi cap
cho phép; full role/delta và relog giống nhau; slot ngoài ownership bị từ chối.

### Task T08: Skill, EXP, evolve, star và formation

**Files:** tạo players/skills.py, teams.py; mở rộng equipment.py, progression.py;
sửa native_commands.py, snapshots.py; content/migrations tương ứng.
**Consumes:** upgradeRoleSkill, useExpItem/Max, evolveEquipment/evolveRole,
upgradeRoleStar/roleBreak và exact formation routes tìm được ở T01.
**Produces:** progression/formation persisted, chung stat projection T03.

- [ ] Map từng request và prerequisite level/rarity/item/skill/cap; không suy diễn roleBreak giống evolveRole.
- [ ] Consume item/coin/SP và nâng trạng thái trong transaction; tombstone bag stack hết; giữ `_temp.preRole` khi consumer cần.
- [ ] Max-EXP không vượt cap hoặc ăn thừa item ngoài luật source; dùng progression rule cùng settlement.
- [ ] Formation chỉ gồm owned living-compatible role, slot unique, không thay frozen team của battle đang chạy.
- [ ] Bổ sung equip/unequip stone/artifact theo exact consumer và ownership; cập nhật release closure trước bật; docs/commit.

**Nghiệm thu:** vật liệu có nguồn T04/T10, không đồ test; upgrade thay stat cả
ở UI và battle; retry không mất thêm vật liệu, client không thể gửi stat tự chọn.

### Task T09: Recruitment ngoài tutorial

**Files:** tạo content/recruitment.py; mở rộng players/recruitment.py;
sửa native_commands.py, snapshots.py, migrations draw/counter/outcome.
**Consumes:** coin/coinTen/gem/gemTen, source101/201 starter và guarantee policy.
**Produces:** draw paid/free/single/ten thật, tutorial marker không lặp.

- [ ] Tách claim_tutorial khỏi draw thông thường; route legacy chỉ claim đúng lần đầu, negotiated command xử lý lượt sau.
- [ ] Import pools/cost/cooldown/guarantee; ghi xung đột EVERY_7/modulo10 thành quyết định owner trước enable.
- [ ] RNG outcome lưu bền trong transaction cùng cost/counters; ten draw là một command với thứ tự mười kết quả cố định.
- [ ] Owned class trùng chuyển đúng asset theo policy, không tạo role trùng unique constraint; đủ content combat của mọi kết quả có thể rơi.
- [ ] Trả `_temp.dropList`, bag/team, cooldown/counter native; docs/commit.

**Nghiệm thu:** retry cùng lượt giữ kết quả; lượt hợp lệ mới không nhận lại Zoro/
Nami guaranteed starter; thiếu tiền không quay; guarantee qua restart không reset.

### Task T10: Bag, compose, useItem và shop

**Files:** tạo economy/inventory.py, shop.py; tái sử dụng economy/boxes.py,
adapters/native_inventory.py; sửa native_commands.py/snapshots.py và content.
**Consumes:** useItem, sell, composeItem/Role, shop.buy/refresh.
**Produces:** native inventory mutations với stable bag IDs, real catalogs.

- [ ] Nối fixed-box handler vào gateway chính dưới same release/command, không bắt client chạy inventory-only session song song.
- [ ] Map item type sử dụng/EXP/AP/box, sell restriction, compose count/recipe;
  reject item không support, không fallback fixed-box cho tất cả kindId.
- [ ] Persist shop catalog version, slot stock, refresh time/cost; client gửi slot
  không được quyết định price; replay giữ đúng hàng cũ khi shop đã refresh.
- [ ] Consume/grant/stock/currency/claim/delta trong transaction; tombstone và
  bag capacity chuẩn consumer; dỡ unavailable UI guard chỉ khi catalog thật đủ.
- [ ] Cập nhật acquisition graph, route ledger, README/CHANGELOG và commit.

**Nghiệm thu:** item dùng/bán không quay lại sau reconnect; refresh retry không
trừ hai lần; inventory đầy không mất box; không có hàng giá0 được bịa để mở UI.

### Task T11: Daily task, achievement và sign-in

**Files:** tạo liveops/tasks.py, sign_in.py; sửa workers/poller.py, snapshots.py,
native_commands.py; additive progress/claims/event-consumer migration.
**Consumes:** committed domain events; receiveTaskAward/receiveTaskActiveAward/signIn.
**Produces:** task progression/claim/counters phản ánh hoạt động thực.

- [ ] Import source definition/requirement/reward, classify daily versus lifetime;
  snapshot có đủ container mà guide/mainTask/QuickNode đọc.
- [ ] Dedup progress bằng eventId/consumer; event chỉ phát sau commit; replay
  equipment/draw/battle không tăng task lần2.
- [ ] Claim khóa player + definition + period, kiểm tra đủ điều kiện và unique
  reward source; active-point claim không lấy client point làm authority.
- [ ] Sign-in reset00:00, daily05:00 Asia/Ho_Chi_Minh; không dùng timezone máy.
- [ ] Ghi delta/task/UI contract, docs và commit.

**Nghiệm thu:** upgrade thực tăng task đúng một lần, claim một lần qua reconnect/
restart; claim ngày cũ không được nhận bằng đổi clock client.

### Task T12: Friends, gifts và friendship stats

**Files:** tạo social/friends.py; sửa snapshots.py/stats.py/native_commands.py;
schema request/pair/gift/date và chỉ mục tìm kiếm.
**Consumes:** toàn bộ friendHandler ở route inventory, hai player có ownership riêng.
**Produces:** request/accept/refuse/remove/list/search/gift single/all.

- [ ] Canonical pair lowerID/higherID, cấm self, enforce request/friend cap;
  tìm kiếm không lộ username/login/token.
- [ ] Khóa hai player theo ID tăng dần; accept cập nhật hai phía cùng transaction;
  concurrent request/accept/remove không có friendship một chiều.
- [ ] Gifts unique(sender,receiver,period), AP ledger khi claim; receiveAll bounded,
  không cấp trùng nếu giao nhau với receiveGift single.
- [ ] Snapshot friendship/stat theo quan hệ thật, xóa friend cập nhật hiệu ứng;
  account revoke kiểm tra lại trước transaction ghi.
- [ ] Native DTO `_temp` theo từng list consumer, docs/commit.

**Nghiệm thu:** owner dùng hai tài khoản thực thấy cùng quan hệ; gift nhận một
lần; người không liên quan không sửa quan hệ hay lấy danh sách private.

### Task T13: Mail, gift code và hoạt động

**Files:** tạo social/mail.py, gift_codes.py, liveops/activities.py;
sửa workers/outbox.py, snapshots.py/native_commands.py; migrations definition/claim.
**Consumes:** mail list/read/receive/removeAllRead/unReadCount, useGiftCode,
receiveActivityAward/updateFreeActivity/activitySaveGem.
**Produces:** inbox/event có definition, schedule, eligibility và reward provenance.

- [ ] Persist mail recipient/sent snapshot; list cursor/bounds, unread thực;
  delete-read không xóa unclaimed reward hoặc thay đổi lịch sử claim.
- [ ] Freeze audience campaign khi dispatch, worker dedup từng recipient;
  receive mail trừ quyền claim và grant cùng transaction.
- [ ] Gift code hash/limit/window/server scope, per-player redemption unique;
  không log raw code; hai entry route dùng một service.
- [ ] Event có version/window/qualification; freeActivity và saveGem theo rule
  riêng; catalog thiếu chưa bật paid card UI, không tạo sale giả.
- [ ] Delta đúng từng consumer, docs/commit; lịch chưa đủ rule ghi BLOCKED_RULE.

**Nghiệm thu:** mail/event/code không claim lặp; restart không gửi lại thưởng;
time window dùng server clock; ngừng event không xóa claim history.

### Task T14: Admin quản trị thật, tách game socket

**Files:** tạo admin/auth.py, rbac.py, audit.py, api.py; `admin-panel/` theo thiết
kế UI riêng khi triển khai; thêm schema admin/audit/approval.
**Consumes:** API/role matrix trong design2026-09-16; domain services T02..T13.
**Produces:** private admin API và UI account/player/economy/content/liveops.

- [ ] Session admin riêng, MFA-ready, server-scoped RBAC; bootstrap operator qua
  secret reference một lần, không public admin registration.
- [ ] Lookup/timeline đọc wallet/inventory/receipt/audit, pagination max100;
  ban/unban/revoke và support notes có actor/reason.
- [ ] Adjustment preview/request/approve, high-value/bulk hai actor khác nhau;
  ledger compensation thay direct wallet edit; audit append-only.
- [ ] Content diff/validate/publish và mail/event schedule dùng immutable version;
  publisher khác runtime, không có ô chạy SQL/raw JSON hoặc player GM route.
- [ ] UI có loading/error/permission/conflict/preview/confirm, secrets không trả
  về browser; docs/commit. Không thiết kế UI thay gameplay native.

**Nghiệm thu:** support-read không grant; người tạo không tự duyệt high-value;
revoked admin không ghi; mọi grant/publish có reason và trace tới ledger/audit.

### Task T15: Finance record và reconciliation, provider disabled

**Files:** tạo payments/orders.py, reconciliation.py, refunds.py, withdrawals.py;
mở admin/api.py, audit.py; schema provider-event/order/reservation/approval.
**Consumes:** state machine/permission của design2026-09-16, same ledger service.
**Produces:** recordkeeping/admin control, không thanh toán hoặc rút tiền thật.

- [ ] Encode order CREATED/PENDING/VERIFIED_PAID/CREDITED và branch failure;
  webhook có verified provider evidence mới được credit, client redirect không đủ.
- [ ] Unique provider event/order reference, amount/currency/SKU/account match;
  credit và qualification top-up reward cùng transaction, retry không credit lại.
- [ ] Refund là compensation liên kết credit; spent-funds cần approved policy;
  unknown provider timeout giữ reconciling, không gửi request mới.
- [ ] Withdrawal disabled: không giả định gem đổi tiền; chỉ enable khi owner
  cung cấp tài sản được rút/provider/pháp lý/KYC/limit/operator approval.
- [ ] Admin timeline/hold/approve separation, docs/commit; không gọi endpoint lịch sử.

**Nghiệm thu:** trạng thái disabled hiển thị rõ; không có success tiền thật tự
tạo; replay/approval policy được code enforce trước khi adapter có thể bật.

### Task T16: Hoàn thiện route expansion theo mode, không đánh dấu chung

**Files:** tạo `docs/protocol/vn-mode-delivery.md`; module trong `battles/`,
`social/` hoặc `liveops/` tương ứng nhóm thật trong inventory; sửa dispatcher/content.
**Consumes:** T01 inventory đầy đủ và authority/reward/progress đã dùng cho SMAP.
**Produces:** ledger cho từng mode cùng implementation chỉ khi đủ native contract.

- [ ] Liệt kê mọi route chưa giao, group theo handler thực: arena/guild/boss/
  expedition/practice và nhóm khác nếu inventory có; ghi exact literals vào mode ledger.
- [ ] Với mỗi nhóm đọc builder/consumer/content trước; ghi entry conditions,
  ticket/attempt/cost, opponent ownership, time window và report/reward rules.
- [ ] Implement từng nhóm thành một commit coherent dùng battle/economy chung;
  guild/multiplayer dùng membership authorization và cross-player lock order.
- [ ] Nếu thiếu data, giao source analysis + rule proposal và code unavailable;
  không xếp hoàn tất hoặc tạo kết quả random để lấp route.
- [ ] Đối chiếu toàn inventory, không chỉ CORE; route DENIED_ADMIN_ONLY luôn bị
  từ chối. README/CHANGELOG ghi mode nào có code, mode nào chưa owner nghiệm thu.

**Done:** tất cả route có implementation hoặc blocker cụ thể được owner chấp
nhận; đây không phải quyền tuyên bố “full game” khi một mode còn thiếu.

**Subtasks bắt buộc từ inventory thật (không bỏ nhóm ít route):**

| Subtask | Handler/count hiện có trong inventory | Trách nhiệm triển khai |
| --- | --- | --- |
| T16.01 | arenaHandler10, arena3v3Handler13 | opponent snapshot, entry/attempt, battle/report/reward, rank transaction |
| T16.02 | expeditionHandler4, sixExpeditionHandler5 | stage chain, team persistence, reset/cost/claim |
| T16.03 | practiceHandler5, sixPracticeHandler5, endlessHandler2 | mode-specific eligibility, progression và reset/reward |
| T16.04 | guildHandler18 | membership/roles/applications/resources, quyền theo guild |
| T16.05 | guildBattleHandler10, newGuildBattleHandler8 | guild roster/window/opponent authority, battle và shared reward |
| T16.06 | worldBossHandler5 | boss/window/damage authority, dedup contribution/claim |
| T16.07 | allServerBattleHandler16, prestigeBattleHandler12, worshipBattleHandler9 | season/server scope, application/rank/battle/claim theo consumer |
| T16.08 | eyeHandler7, tailHandler2 | đọc source xác định nghĩa mode, asset/cost và consumer trước khi thiết kế domain |
| T16.09 | rankHandler2, videoHandler7 | rank persisted và replay/report ownership; không public raw player/token |
| T16.10 | route còn lại của playerHandler22, teamHandler21, bagHandler11 | profile/avatar/ship/title và từng literal chưa được T03/T06/T08/T10/T11/T13 giao |

Mỗi subtask áp dụng toàn bộ năm bước T16 và có commit/status riêng; số route là
kiểm kê tĩnh, không là tỷ lệ hoàn thành. Không đoán `eye`/`tail` bằng tên tiếng Anh.
T01 gắn mỗi literal vào đúng task/subtask; năm bootstrap routes, point4, friend12,
mail7, shop2 và smap6 được đối chiếu ở task tương ứng; gm3 luôn denied.

### Task T17: Production config, ACL và transport

**Files:** tạo runtime/config.py, content/release.py, deploy/production.example.json;
sửa db/session.py, db/native_permissions.py, native_setup.py, content/native_battles.py,
adapters/native_gateway.py, native_metadata.py, pomelo_transport.py, cli.py.
**Consumes:** profile owner cấp, source/release/artifact pins và current safeguards.
**Produces:** production profile opt-in, không phá guards test/development cũ.

- [ ] Parse profile file strict: environment, DB host/name/schema/secretRef,
  bind endpoints, advertised auth/metadata/gate/connector, allowed TLS origins;
  unknown key/loopback advertisement/public DB/superuser runtime phải fail.
- [ ] Tách internal bind và advertised connector; gate không trả internal IP cho
  APK. Proxy WebSocket path/heartbeat/upgrade đúng codec; không trust Forwarded tùy ý.
- [ ] Mở rộng target validators có allowlist production explicit, không thay
  bằng `return True`; production không dùng fallback kbht_admin/kbht_dev.
- [ ] Runtime/worker/migrator/publisher/admin grants riêng; publication đọc
  compatibility report, pin content/engine/client protocol, từ chối mismatch.
- [ ] Thêm CLI `serve-native --profile`, `release inspect/prepare/activate`,
  `migrate --profile` theo runbook contract; không tự chạy activation. Docs/commit.

**Nghiệm thu:** code có thể cấu hình online mà không sửa hardcoded source;
chưa cấp profile thì fail closed; public ingress không làm DB/admin thành public.

### Task T18: APK online release profile, giữ nguyên engine

**Files:** tạo patches/online-endpoints.js, tools/apk-recovery/prepare-online-endpoints.py;
sửa build-repacked.ps1, stage-client-patches.py; docs/client release contract.
**Consumes:** T17 endpoint allowlist, command/battle capabilities, signing secret ref.
**Produces:** `-OnlineProfile` độc lập Lab flags, release APK+manifest matched.

- [ ] Thêm profile stage auth/config/manifest/gate/connector; không sửa src,
  không copy toàn source sang project Cocos mới và không sửa `.so` để giả recovery.
- [ ] Đổi builder validation để online profile dùng native patches mà không cần
  LabBootstrap/LabLocalAuth; cấm trộn inventory-only và native full gateway.
- [ ] Trace socket construction `ws://` và HTTP consumers; stage HTTPS/WSS nhất
  quán với native TLS support; không bypass certificate validation.
- [ ] Disable historical SDK/analytics/provider calls qua narrow source pins;
  validate resolved host sau alias resolution, không chỉ hostname đầu vào.
- [ ] Build/sign chỉ khi owner yêu cầu artifact, pin key identity và version;
  không install/launch. Package report và docs phân biệt PACKAGED/OWNER_ACCEPTED.

**Nghiệm thu:** artifact/config/manifest/command protocol cùng release; không
có đường fallback về provider hoặc loopback trong online profile. Native TLS chưa
owner xác nhận phải ghi NOT_RUN, không suy ra từ khả năng Python TLS.

### Task T19: Service packaging, health, backup và restore

**Files:** tạo ops/health.py, release.py, backup.py, restore.py, deploy/production.compose.yml,
deploy/proxy.conf, deploy/service unit theo platform owner chọn; sửa worker lifecycle/CLI.
**Consumes:** profile và release T17, APK T18, existing outbox leases.
**Produces:** immutable app/worker artifact, readiness/metrics, operator commands.

- [ ] Package deps pinned + Node engine artifact; non-root, bounded CPU/process/
  timeout, private DB, graceful drain, expire worker leases đúng restart.
- [ ] Readiness kiểm tra schema/content/engine/profile/DB role; log redaction,
  correlation ID và metric settlement failure/outbox lag/backup age.
- [ ] Backup encrypted base+WAL với manifest time/hash/schema/release/last position;
  rotation không xóa bản đang dùng để restore, secret ngoài command line.
- [ ] Restore dry-plan bắt buộc explicit target khác active DB; operator approval
  cho actual restore/switch; không tự chạy rehearsal hoặc overwrite current DB.
- [ ] Thêm CLI ops/status/backup-plan/backup/restore-plan/restore theo runbook,
  ghi retention/RPO/RTO là mục tiêu chưa đo, docs/commit.

**Nghiệm thu:** operator có đúng artifact, start/stop/status, drain/rollback và
backup references; không tự nhận 500CCU/p95/RTO khi chưa có số đo owner cho phép.

### Task T20: Release manifest và bàn giao vận hành

**Files:** tạo `docs/release/online-release-status.md`; sửa route ledger,
README.md, CHANGELOG.md, server-online/README.md, client-recovered/README.md, runbook.
**Consumes:** artifact hashes, task ledger, owner environment và approvals.
**Produces:** release candidate và danh sách missing owner acceptance theo route.

- [ ] Manifest gồm Git SHA, source/APK/manifest/engine/rules hashes, schema revision,
  protocol capabilities, content release, dependency lock hash, signing identity.
- [ ] Kiểm tra tài liệu không còn active pointer tới Lab runbook; giữ file cũ
  dạng historical, không sửa báo cáo quá khứ thành đã triển khai online.
- [ ] Owner cấp deployment inputs rồi mới thực hiện runbook activation riêng;
  chưa có thì ghi code/package-ready, không tạo domain/host hay chạy migrate ngầm.
- [ ] Bàn giao APK/backend pair và acceptance checklist cho owner: auth/relog,
  battle/reward, upgrade, recruit, tasks, friends, mail/events, admin; record đúng
  release/account pseudonym/expected/observed, không token/raw password.
- [ ] Mỗi lỗi owner báo quay về task/route tương ứng; chỉ đóng OWNER_ACCEPTED
  sau bằng chứng thao tác và persistence. Commit/push bình thường, không force.

## E. Self-review và điều kiện kết thúc

| Phần spec | Task chịu trách nhiệm |
| --- | --- |
| Baseline/provenance/request+consumer | T01, T03, T04, T09, T16 |
| Authority, durable retry, exact DTO | T02 và mọi mutation T05..T16 |
| Core gameplay/progression | T03..T13 |
| Admin/finance | T14, T15 |
| Remaining modes | T16, từng dòng mode ledger |
| Real online transport/APK | T17, T18 |
| Operations/release/status honesty | T19, T20 |

Plan không đề nghị chạy lab, broad tests hoặc tự deploy. Những chỗ thiếu luật
được xác định rõ đầu vào và đường xin quyết định, không được bịa implementation.
Sau mỗi task cập nhật ledger tracked và commit có README/CHANGELOG; tiếp tục task
độc lập kế tiếp, không viết lại plan thay cho code. Cần tài liệu dependency khi
thực thi thì dùng Context7 theo AGENTS, không nâng stack chỉ vì docs mới hơn.
