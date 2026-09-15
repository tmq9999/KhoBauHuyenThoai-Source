# Kho Báu Huyền Thoại — APK client recovery

Phát triển trực tiếp từ APK Việt Nam. Không có web/demo thay thế.

## Xây dựng server online

Mục tiêu tiếp theo là game server online có database authoritative và admin
panel. Hướng kiến trúc đã được Owner duyệt; **chưa triển khai hệ thống production**.
Codex bắt đầu từ M0 trong các tài liệu sau:

- [Runbook triển khai bằng Codex](docs/superpowers/runbooks/2026-09-16-codex-online-game-server.md).
- [Spec server, database, client và admin](docs/superpowers/specs/2026-09-16-online-game-server-design.md).
- [Plan M0–M10](docs/superpowers/plans/2026-09-16-online-game-server.md).
- [Review lỗi và route](docs/protocol/vn-online-route-matrix.md).

Mỗi commit bàn giao phải cập nhật README và [CHANGELOG](CHANGELOG.md) trong
cùng commit; kiểm lại cả hai sau commit. Test server và kiểm chứng trên APK phải
được báo riêng. Antigravity chưa dùng ở giai đoạn này; tài liệu recovery cũ giữ
làm bằng chứng, không phải runbook triển khai online hiện hành.

Repo GitHub: [tmq9999/KhoBauHuyenThoai-Source](https://github.com/tmq9999/KhoBauHuyenThoai-Source),
đã xác minh **Private** ngày 2026-09-16. Nhánh source hiện tại:
`feat/native-game-entry`; giữ nguyên lịch sử recovery. Đây là bản lưu source và
kế hoạch, không phải release production. Không upload keystore, APK, database,
backup hoặc logcat lên Git.

## Source phục hồi

- [project.js](client-recovered/src/project.js): 6,039,275 bytes JavaScript giải từ project.jsc.
- [settings.js](client-recovered/src/settings.js): scene/UUID/resource settings;37scene gồm36product +1test.
- [jsb_polyfill.js](client-recovered/src/jsb_polyfill.js): engine runtime ghi1.10.3.
- [Client build hướng dẫn](client-recovered/README.md).

## Build lại APK

~~~powershell
pwsh -NoProfile -File client-recovered/scripts/build-repacked.ps1 -LabBootstrap -LabLocalAuth -Sign
~~~

Script kiểm hash APK/native/tool, encode source về JSC, stage và đóng gói/ký bằng key lab riêng. Không cài hoặc chạy APK. Native .so vẫn là prebuilt, chưa phải project Cocos editor/C++ hoàn chỉnh.

Thêm `-CreateDebugKeystore` chỉ khi key lab trong project chưa tồn tại. Bản
không có `-LabBootstrap -LabLocalAuth` giữ endpoint gốc, không dùng để chạy lab.

[APK lab cài lại ngày 2026-09-16](work/apk-vn/20260915T112626Z-repack-first-map-runtime/artifacts/vn-recovered-debug-signed.apk) · [Báo cáo build](work/apk-vn/20260915T112626Z-repack-first-map-runtime/repack-build-report.md)

SHA-256: `f5564e5c375266ec41258d3dc4729c6ce2550cc420f2548ff537b6798a042156`.
Artifact trong `work/` chỉ có local, không có trong checkout mới từ GitHub.

## Chạy client/server hiện tại

[Lệnh chạy server và nối emulator-5554](server-compatible/README.md). Runner là
`server-compatible/src/game_server.py`, dùng SQLite lưu tài khoản/nhân vật;
không chạy `probe_server.py` để chơi.

Client phục hồi đã vào home/đội hình trên MuMu `emulator-5554`. Code lab hiện có
SMAP 10101–10106, chiêu mộ tutorial, một phần inventory/EXP/điểm danh/tiến bậc xanh.
Owner vẫn xác nhận lỗi lực chiến số lẻ, qua map, chiêu mộ thật, nâng cấp trang bị,
bạn bè, daily task và mua Beli. Database PostgreSQL, combat authoritative và
admin panel **chưa tồn tại**. Không gọi kết quả này là game online hoàn chỉnh.

Runner hiện có, giữ đúng state cũ và manifest cùng APK (không bật hai instance):

~~~powershell
python -u server-compatible/src/game_server.py --manifest work/apk-vn/20260915T112626Z-repack-first-map-runtime/lab-bootstrap/project.manifest --state work/apk-vn/20260915T001024Z-game-entry/runtime/game-playable3.sqlite3
~~~

Sau restart server phải đăng nhập lại vì token lab ở RAM. Không xoá DB/app data
để xử lý lỗi. Backup trước khi migrate; chỉ nhập vào DB đích mới.

## Kiểm tra

~~~powershell
python -m pytest -q tests server-compatible/tests/protocol -p no:cacheprovider
git diff --check
~~~

Không chạy `pytest` không chỉ định thư mục: `work/` chứa bản sao test lịch sử.
Kiểm lại ngày 2026-09-16: 215 passed, 3 skipped; không phải bằng chứng mọi chức
năng client hoạt động. Bản source này gồm feature slice lab và tài liệu Codex;
việc lưu lên GitHub không bổ sung hay xác minh gameplay mới.

[Contract và phạm vi đã kiểm](docs/protocol/vn-client-server-contract.md).
Giữ firewall chặn provider/payment và dùng đúng lab đã được chọn; không cài
lên thiết bị thật. Sau restart emulator cần tạo lại bốn ADB reverse mappings.

[Mốc recovery](docs/release/2026-09-14-native-recovery-milestone.md) · [Plan recovery lịch sử](docs/superpowers/plans/2026-09-14-vn-apk-client-reconstruction.md)
