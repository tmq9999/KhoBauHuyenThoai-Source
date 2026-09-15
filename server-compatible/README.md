# Server local cho client APK Việt Nam

Runner sử dụng thật là **`src/game_server.py`**, không phải `probe_server.py`.
Client native đã đăng nhập, vào home, đặt tên, nhận Luffy/Zoro/Nami và mở màn
chọn đội hình. Trận đầu đang được nối theo protocol APK; chưa có toàn bộ game.

## Chạy server

Từ `D:\GeminiWorkspaceNew\KhoBauHuyenThoai`, dùng Python 3.12 đã có sẵn:

```powershell
python -u server-compatible/src/game_server.py --manifest work/apk-vn/20260915T112626Z-repack-first-map-runtime/lab-bootstrap/project.manifest --state work/apk-vn/20260915T001024Z-game-entry/runtime/game-playable3.sqlite3
```

Giữ cửa sổ này mở. Nếu báo cổng đang được sử dụng, server cũ vẫn chạy; không
khởi động thêm instance hoặc đổi sang SQLite mới. Dừng đúng tiến trình runner
trước khi nạp code mới. Giữ nguyên `--state` để giữ tài khoản và tiến độ.
Session token chỉ ở RAM: sau mỗi lần restart server cần đăng nhập lại client.
Không cần Docker, Node hay dependency runtime ngoài Python stdlib.

| Cổng (chỉ `127.0.0.1`) | Chức năng |
|---|---|
| 20001 | config, notice, update manifest đúng bản APK lab |
| 20003 | tài khoản local và server list |
| 20100 | Pomelo gate |
| 20101 | connector, player, tutorial |

Manifest ở trên phải đi cùng APK lab cùng run. `work/` và APK không nằm trong
Git: checkout trên máy khác cần input APK/baseline và build lại client để có
manifest/artifact mới; không dùng một manifest ngẫu nhiên.

## Nối đúng emulator-5554

Chỉ dùng MuMu lab đã được Owner chọn. Phải giữ hai luật firewall
`KBHT-MuMu-egress-temp-device` và `KBHT-MuMu-egress-temp-main` ở trạng thái
Enabled/Block; không mở provider/payment gốc. Không tắt Wi-Fi guest vì có thể
làm mất kết nối ADB của MuMu.

Chạy lại bốn lệnh reverse sau mỗi lần restart emulator:

```powershell
$adb = 'C:/Users/tranm/AppData/Local/Android/Sdk/platform-tools/adb.exe'
& $adb -P 5037 -s emulator-5554 reverse tcp:20001 tcp:20001
& $adb -P 5037 -s emulator-5554 reverse tcp:20003 tcp:20003
& $adb -P 5037 -s emulator-5554 reverse tcp:20100 tcp:20100
& $adb -P 5037 -s emulator-5554 reverse tcp:20101 tcp:20101
& $adb -P 5037 -s emulator-5554 reverse --list
& $adb -P 5037 -s emulator-5554 shell am start -n com.kbht.gg/org.cocos2dx.javascript.AppActivity
```

APK lab cài lại ngày 2026-09-16: `work/apk-vn/20260915T112626Z-repack-first-map-runtime/artifacts/vn-recovered-debug-signed.apk`.
SHA-256: `f5564e5c375266ec41258d3dc4729c6ce2550cc420f2548ff537b6798a042156`.
Mở đăng nhập local, dùng tài khoản lab hiện có, đóng thông báo, chọn vào game.
Không cài bản này lên máy/tài khoản thật; không xoá dữ liệu app để sửa lỗi mạng.

## Kiểm tra

```powershell
python -m pytest -q server-compatible/tests/protocol -p no:cacheprovider
```

`probe_server.py` vẫn được giữ cho test transport độc lập; nó cố ý trả lỗi cho
application routes và không dùng để chơi game. Game runner là backend tương
thích cục bộ, không phải source server lịch sử. Hiện runner hỗ trợ slice game-entry
đầu tiên: lực chiến/trạng thái đồng đội, SMAP 10101-10106 với phần thưởng vật
phẩm, điểm danh theo ngày, dùng/bán vật phẩm, EXP đồng đội và tiến bậc xanh.
Tiến bậc cần đủ nguyên liệu; nguồn kiếm một số nguyên liệu (49902) chưa được nối.
Runner đã được khởi động lại ngày 2026-09-16, nhưng Owner vẫn xác nhận các lỗi
gameplay trong [route matrix](../docs/protocol/vn-online-route-matrix.md).
Test loopback không thay thế nghiệm thu đầy đủ trên APK thật.
Các event ngoài điểm danh, shop, task, multiplayer và tier sau chưa được triển khai.
Xem [chi tiết kiểm thử và giới hạn](../docs/release/2026-09-15-server-feature-slice.md)
và [contract](../docs/protocol/vn-client-server-contract.md).
