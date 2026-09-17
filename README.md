# Kho Báu Huyền Thoại Source

## Snapshot lưu mã nguồn 2026-09-17

Owner yêu cầu commit toàn bộ thay đổi hiện có và push nhánh
`feat/native-game-entry`. Đây là snapshot công việc đang triển khai, không phải
release backend hoàn chỉnh. Không chạy lại test, emulator, build APK hoặc DB
trong lần lưu này. Giữ nguyên các test và bằng chứng đã có trong repository.
Secrets, database, APK sinh ra và dữ liệu runtime đang ignore không được thêm
vào Git. Remote hiện tại là repository private; source phục hồi đã có trên
remote không bị chỉnh sửa. Việc lưu nhánh không cho phép công khai source/khóa SDK.

Source hiện đã có migration0016, begin/end SMAP, kết toán ledger và staged
NativeBattle hook; native10106→10107 và phát hành online vẫn chưa được xác nhận.
Các ghi chú cũ bên dưới mô tả từng checkpoint, không phải trạng thái release.

Mã nguồn client Android phục hồi từ APK Kho Báu Huyền Thoại, server tương thích
protocol native và package backend PostgreSQL. Client sử dụng JavaScript,
Android glue, resources và thư viện native Cocos 1.10.3 từ APK gốc.

## Kiến trúc kỹ thuật

**Bàn giao Antigravity:** mở [runbook tiếp tục triển khai](docs/superpowers/runbooks/2026-09-17-antigravity-online-backend.md)
và copy prompt đầu file vào phiên mới. Bản này trỏ đúng spec/plan hiện hành,
khôi phục progress và bắt đầu T01/T02 nếu chưa được thực hiện.

Hướng triển khai hiện hành: [đặc tả backend online](docs/superpowers/specs/2026-09-17-apk-online-backend-delivery.md),
[plan 20 task](docs/superpowers/plans/2026-09-17-apk-online-backend-delivery.md) và
[runbook triển khai](docs/superpowers/runbooks/2026-09-17-apk-online-backend-delivery.md).
Owner yêu cầu thực hiện code sản phẩm, không Lab/emulator/ADB hoặc broad test
loops. Bộ mới chỉ rõ phần code đã có, luật loot/chiêu mộ còn thiếu, command retry,
gameplay, admin và production transport/backup. Bước thực thi kế tiếp là T01/T02.
Lệnh production và `-OnlineProfile` trong runbook là giao diện cần triển khai,
chưa có trong CLI/builder hiện tại. Chưa triển khai public server.
Server phải nhận đúng form `/user/*` và Pomelo của APK phục hồi, với PostgreSQL
là nguồn ghi duy nhất. Runner SQLite chỉ được giữ làm bằng chứng lịch sử.
Rules mở đầu đã được version hóa tại
[native-opening-v1](docs/protocol/vn-native-opening-v1.md); đây là các lựa chọn
server mới được nêu rõ, không nhận là backend lịch sử đã phục hồi.
Lần chạy native PostgreSQL và artifact tương ứng được ghi tại
[native PostgreSQL opening](docs/release/2026-09-17-native-postgres-opening.md).
Mốc opening là tạo nhân vật/home/đổi tên; chiêu mộ tutorial có
[báo cáo riêng](docs/release/2026-09-17-native-postgres-tutorial.md).
Chiến đấu1-7 chưa được nghiệm thu native.
Engine chiến đấu đang dùng module logic phục hồi từ chính client, tách khỏi
SDK/UI và chạy theo seed/input xác định. Code settlement và staged native battle
đã có trong snapshot990d8dc; còn luật loot, publication/production và nghiệm thu
APK. Mô phỏng chạy được không đồng nghĩa APK đã qua ải1-7.
Patch `-NativeAvailability` bảo vệ consumer gốc khi server đang bảo trì hoặc
catalog shop/thẻ chưa có; không tạo hàng giả và không thay cho triển khai gameplay.
Chi tiết cờ build ở [client-recovered/README](client-recovered/README.md).

The explicit `serve-inventory` command provides a bounded loopback WebSocket /
Pomelo inventory listener at `/inventory` (default port21002). It connects the
negotiated session/command boundary to PostgreSQL; it does not seed, migrate,
publish content or replace the existing native bootstrap service. The ES5
inventory bridge can be embedded into a fresh staged APK with `-InventoryBridge`.
Activation still requires a trusted online bootstrap; the flag does not convert
existing SQLite sessions or create a complete online login flow.

Fixed material-box use is available as a transactional Python handler
(`inventory.useFixedBox` when explicitly registered): it consumes an owned box,
grants its published recipe through the shared reward ledger, and saves the
result for safe retries. Random boxes and an actual box-acquisition loop remain
pending. The default HTTP listener exposes no gameplay routes; the separate
opt-in inventory listener allows the bounded useItem route. Content publication
is never performed automatically.

The opt-in native inventory adapter translates `{bagIndex,itemCount}` to the
fixed-box service and returns `bag.items`/`_temp.entityCountMap`. Fresh online
inventories use stable decimal-string PostgreSQL IDs; legacy bag migration and
full player bootstrap are still pending. See
[native inventory contract](docs/protocol/vn-native-inventory-adapter.md).

`InventoryConnection` adds per-connection token validation, capability/selection
negotiation and reconnect bag snapshots around that adapter. Commands remain
bound to the selected player/server/content; reconnect retries retain original
command IDs and versions. The separate Pomelo inventory listener wraps this
connection; neither provides full player login.

The next bootstrap boundary is documented in
[online bootstrap contract](docs/protocol/vn-online-bootstrap.md). Its `/v1`
JSON endpoints are separate from the recovered client's form `/user/*` calls.
An inventory-only snapshot is not a replacement for native player entry.
The opt-in `serve-bootstrap` command binds loopback21003 for account creation,
Argon2id login, session revoke and authenticated existing-player inventory
selection. It requires explicit schema migration through0013 and does not seed
players/content or launch a public service. See backend setup instructions.

Content staging supports `prepare-content --environment test --import-id <UUID>`
to create a replayable PostgreSQL DRAFT with normal-map definitions and ordered
mob-wave references. Chapter relationships determine map order, including
10106 -> 10107 and 10112 -> 10201; ID ranges are not used to classify normal maps.
Preparation does not activate content or open a game server.

`import-dependencies` archives seven hash-verified combat/item tables and their
reference audit in PostgreSQL. Ordered raw cells preserve duplicate definitions
instead of choosing one silently. The report exposes blockers separately from
successful archive storage; `publishable` remains false. See
[dependency evidence](docs/protocol/vn-combat-content-dependencies.md).

`prepare-equipment` builds a separate equipment-only DRAFT: validated evolution
chains, target-tier ingredient quantities and original entity metadata. It does
not grant materials or enable upgrades; combat and acquisition gates still apply.

`audit-acquisition` validates drop-class/box references and archives per-material
source candidates. Fixed quantities remain separate from random weights/rates;
zero-count rows and unverified sources are not treated as gameplay rewards.
See [material source evidence](docs/protocol/vn-material-acquisition.md).

`server-online` includes a command-envelope adapter backed by the PostgreSQL
executor and a loopback HTTP transport (`/health`, `/v1/command`). The transport
resolves bearer tokens through the durable session service; gameplay routes are
denied unless explicitly registered. Account registration/password verification
are exposed only by the separate opt-in `serve-bootstrap` listener. HTTP command,
bootstrap and inventory Pomelo are separate listeners; no native gameplay
cutover has occurred.

`server-online/src/kbht_server/content/` reads hash-verified APK literals,
preserves sparse chapter rows and raw fields, validates chapter/stage order and
stores draft projections atomically. Replay rejects changed or missing rows.
Mob/skill/item reference validation, publication and native gameplay remain
pending. See [content provenance](docs/protocol/vn-normal-map-content.md).

```text
Native APK -> HTTP / Pomelo-WebSocket -> server-compatible -> SQLite

Inventory bridge / CLI -> server-online -> PostgreSQL
                            |
                            +-> command receipts / ledger / outbox / leased poller
```

Hai backend có entry point và database riêng, không dual-write.
`server-compatible` phục vụ kết nối APK; `server-online` cung cấp CLI và core
transaction Python. Kiến trúc đích gồm native adapter, game services, worker,
Redis và admin API/UI được mô tả trong
[đặc tả online server](docs/superpowers/specs/2026-09-16-online-game-server-design.md).

## Cấu trúc repository

| Thư mục | Trách nhiệm |
| --- | --- |
| `client-recovered/` | JavaScript/resources/glue phục hồi, script build và patch có kiểm soát |
| `server-compatible/` | Runner SQLite phục vụ lab protocol và migration reference |
| `server-online/` | Package server PostgreSQL, migrations, command contracts và integration tests |
| `tools/protocol/` | Route inventory và kiểm tra provenance protocol |
| `tools/apk-recovery/` | Decoder, staging, patch và repack APK |
| `tools/ci/` | Kiểm tra delivery docs và các gate CI |
| `tests/` | Test phục hồi APK, protocol, client patch và tooling |
| `docs/protocol/` | Route matrix, consumer contract, inventory và wire evidence |
| `docs/superpowers/specs/` | Đặc tả kiến trúc và ranh giới an toàn |
| `docs/superpowers/plans/` | Kế hoạch triển khai theo milestone |
| `docs/superpowers/runbooks/` | Quy trình vận hành dành cho Codex |
| `docs/agent-runs/` | Nhật ký tiến độ, bằng chứng, blocker và quyết định theo phiên |
| `docs/release/` | Báo cáo build/recovery và acceptance theo release |

## Hợp đồng dữ liệu chính

Mutating command dùng các trường `command_id`, `account_id`, `player_id`,
`server_id`, `route`, `expected_version`, `content_version_id` và `payload`.
`CommandExecutor` khoá player, kiểm tra ownership/version/content, chạy handler
và commit wallet, ledger, receipt, outbox trong cùng transaction. Retry nguyên
command nhận lại kết quả đã lưu; cùng key nhưng envelope khác trả `CONFLICT`.

- `wallets`: số dư nguyên `BIGINT`, khóa `(player_id, currency)`.
- `ledger_transactions`, `ledger_postings`, `wallet_ledger`: bút toán theo
  command và đối ứng issuance/sink theo currency.
- `command_receipts`: khóa `(player_id, command_id)`, hash input và saved result.
- `outbox_events`: event ghi cùng transaction với thay đổi domain.
- `worker_receipts`: khóa `(consumer, event_id)`, ghi cùng transaction với xử
  lý event để retry không áp dụng thay đổi lần hai.
- `item_definitions`, `inventory_items`, `inventory_ledger`: định nghĩa theo
  content version, stack theo chủ sở hữu và lịch sử số lượng bất biến.
- `reward_grants`, `reward_items`, `reward_currencies`: cấp thưởng duy nhất theo
  người chơi/loại nguồn/UUID nguồn; ghi cùng transaction với inventory và wallet.
- `db/permissions.py`: cấp quyền rõ ràng cho role runtime không sở hữu schema;
  migration và runtime sử dụng hai phạm vi quyền khác nhau.
- Account/content/command/event dùng UUID; player dùng số nguyên an toàn cho JS.
- Timestamp dùng `timestamptz`, kết nối PostgreSQL dùng UTC.

Đặc tả đầy đủ nằm trong
[online-game-server-design](docs/superpowers/specs/2026-09-16-online-game-server-design.md)
và [client-server contract](docs/protocol/vn-client-server-contract.md).

## Cài đặt môi trường

- Windows với PowerShell.
- Python `3.12.x` cho tooling và compatibility runner.
- Python virtual environment `server-online/.venv` cho online server.
- Android SDK/platform-tools nếu kiểm tra APK trên MuMu lab.
- PostgreSQL 18 cho backend online; lab mặc định `127.0.0.1:25432`.
- Node.js cho test JavaScript; JDK/Android build-tools cho repack/sign APK.

Từ repository root, tạo virtual environment và cài package:

```powershell
python -m venv server-online/.venv
& '.\server-online\.venv\Scripts\python.exe' -I -m pip install --require-hashes -r server-online/requirements.lock
& '.\server-online\.venv\Scripts\python.exe' -I -m pip install --no-deps --editable ./server-online
```

Lockfile dành cho Windows x64/Python 3.12. Backend đọc biến môi trường của
process; cấu hình và cách chạy PostgreSQL ở [server-online/README](server-online/README.md).

## Migration và kiểm tra database

Các lệnh dưới đây chạy từ repository root. `KBHT_DB_PASSWORD_FILE` trỏ tới file
secret local đã được cấp quyền riêng; không đưa password vào command line.

```powershell
$env:KBHT_DB_PASSWORD_FILE = (Resolve-Path 'work/m1-env/secrets/postgres-superuser.txt').Path
& '.\server-online\.venv\Scripts\python.exe' -I -m kbht_server.cli migrate --environment development
& '.\server-online\.venv\Scripts\python.exe' -I -m kbht_server.cli check-invariants --environment development
& '.\server-online\.venv\Scripts\python.exe' -I -m pytest -q server-online/tests -p no:cacheprovider
Remove-Item Env:KBHT_DB_PASSWORD_FILE
```

Portable PostgreSQL lab dùng database `kbht_dev`/`kbht_test` trên loopback port
`25432`. Chi tiết start/stop, package install, migration và test contract ở
[server-online/README](server-online/README.md). Migrations không được chạy vào
SQLite compatibility database.

## Chạy compatibility runner và APK lab

Runner nhận manifest cùng bản APK và đường dẫn SQLite lưu tài khoản/nhân vật:

```powershell
python -u server-compatible/src/game_server.py --manifest "$env:KBHT_LAB_MANIFEST" --state "$env:KBHT_LAB_STATE"
```

Đặt `KBHT_LAB_MANIFEST` và `KBHT_LAB_STATE` theo cấu hình lab trong
[hướng dẫn runner](server-compatible/README.md). Session ở RAM, nên sau restart
runner cần đăng nhập lại. Các cổng loopback: `20001` static/config, `20003` auth,
`20100` gate, `20101` connector.

Build/repack APK từ source phục hồi (cần input APK/baseline cục bộ):

```powershell
pwsh -NoProfile -File client-recovered/scripts/build-repacked.ps1 -ValidateOnly
pwsh -NoProfile -File client-recovered/scripts/build-repacked.ps1 -LabBootstrap -LabLocalAuth -Sign
```

Builder tạo artifact và manifest trong `work/apk-vn/<run>/`; không cài ứng dụng.
Tuỳ chọn `-PowerDisplay` đi cùng hai cờ lab để patch formatter lực chiến.
Thêm `-InventoryBridge` để nhúng bridge và hook socket vào bản staged; không
sửa `client-recovered/src/project.js`. Runtime phải cung cấp session PostgreSQL,
player/server/content khớp, nguồn UUID an toàn và callback ngắt writer SQLite.
Không tự bật bridge bằng token hoặc inventory cũ.
Xem [hướng dẫn client](client-recovered/README.md) về signing và
[hướng dẫn runner](server-compatible/README.md) về ADB reverse trên MuMu.

Luồng chạy APK trên MuMu và ranh giới backend được ghi tại
[native lab smoke](docs/release/2026-09-17-native-visible-smoke.md).
Không dùng kết quả runner SQLite để nghiệm thu gameplay PostgreSQL.

## Kiểm tra tooling và protocol

```powershell
python -m pytest -q tests server-compatible/tests/protocol -p no:cacheprovider
node --test tests/client/test_power_display.mjs
python tools/protocol/route_inventory.py --source client-recovered/src/project.js --output docs/protocol/vn-route-inventory.json --check --consumers docs/protocol/vn-core-consumers.json
python tools/ci/check_delivery_docs.py --base "$env:KBHT_DOCS_BASE" --head HEAD
```

Chỉ định thư mục test để loại artifact/runtime trong `work/` khỏi discovery.
`KBHT_DOCS_BASE` là commit mốc cần kiểm. Test online dùng PostgreSQL `kbht_test`
và tạo schema riêng cho mỗi test; không dùng database SQLite của runner.

## Tài liệu dự án

- [Online server specification](docs/superpowers/specs/2026-09-16-online-game-server-design.md)
- [Codex implementation plan](docs/superpowers/plans/2026-09-16-online-game-server.md)
- [Codex runbook](docs/superpowers/runbooks/2026-09-16-codex-online-game-server.md)
- [Route and defect matrix](docs/protocol/vn-online-route-matrix.md)
- [Protocol contract](docs/protocol/vn-client-server-contract.md)
- [Online-server progress log](docs/agent-runs/online-server-progress.md)
- [Native client build guide](client-recovered/README.md)
- [Compatibility runner guide](server-compatible/README.md)
- [Change history](CHANGELOG.md)
