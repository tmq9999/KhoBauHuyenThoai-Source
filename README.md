# Kho Báu Huyền Thoại Source

Mã nguồn client Android phục hồi từ APK Kho Báu Huyền Thoại, server tương thích
protocol native và package backend PostgreSQL. Client sử dụng JavaScript,
Android glue, resources và thư viện native Cocos 1.10.3 từ APK gốc.

## Kiến trúc kỹ thuật

```text
Native APK -> HTTP / Pomelo-WebSocket -> server-compatible -> SQLite

CLI / Python commands -> server-online -> PostgreSQL
                            |
                            +-> command receipts / ledger / outbox
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
Xem [hướng dẫn client](client-recovered/README.md) về signing và
[hướng dẫn runner](server-compatible/README.md) về ADB reverse trên MuMu.

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
