# Kho Báu Huyền Thoại — APK client recovery

Phát triển trực tiếp từ APK Việt Nam. Không có web/demo thay thế.

## Source phục hồi

- [project.js](client-recovered/src/project.js): 6,039,275 bytes JavaScript giải từ project.jsc.
- [settings.js](client-recovered/src/settings.js): scene/UUID/resource settings;37scene gồm36product +1test.
- [jsb_polyfill.js](client-recovered/src/jsb_polyfill.js): engine runtime ghi1.10.3.
- [Client build hướng dẫn](client-recovered/README.md).

## Build lại APK

~~~powershell
pwsh -NoProfile -File client-recovered/scripts/build-repacked.ps1 -Sign -CreateDebugKeystore
~~~

Script kiểm hash APK/native/tool, encode source về JSC, stage và đóng gói/ký bằng key lab riêng. Không cài hoặc chạy APK. Native .so vẫn là prebuilt, chưa phải project Cocos editor/C++ hoàn chỉnh.

[APK ký debug đã build](work/apk-vn/20260914T142000Z-repack/artifacts/vn-recovered-debug-signed.apk) · [Báo cáo build](work/apk-vn/20260914T142000Z-repack/repack-build-report.md)

## Server và bước tiếp theo

[server-compatible](server-compatible/README.md) mới có codec/Pomelo probe dựa trên source thực, chưa có login/gameplay thành công. [Contract static](docs/protocol/vn-client-server-contract.md) phân biệt message đã đọc và dữ liệu chưa biết.

Chưa cài/chạy trên emulator hoặc thiết bị thật. Bước tiếp: lab disposable chặn egress → boot chính APK phục hồi → xác minh scene/requests → triển khai nhóm server messages. Không chạy APK lên thiết bị ADB của người dùng nếu chưa được phép.

[Kết quả triển khai](docs/release/2026-09-14-native-recovery-milestone.md) · [Plan hiện hành](docs/superpowers/plans/2026-09-14-vn-apk-client-reconstruction.md)
