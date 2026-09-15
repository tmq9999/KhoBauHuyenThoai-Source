# VN APK Client Reconstruction — Spec

Ngày: 2026-09-14. Phạm vi người dùng yêu cầu: decompile/phục hồi đúng client từ APK, rồi server tương thích. Các task tương lai chưa hoàn thành.

[Plan](../plans/2026-09-14-vn-apk-client-reconstruction.md) · [Runbook](../runbooks/2026-09-14-antigravity-vn-apk-client-reconstruction.md) · [Output decompile thật](../../reverse-engineering/20260914T180000Z-vn-apk-static-report.md)

## Mục tiêu

Phục dựng client Android/Cocos có thể build và khởi động dựa trên APK/KhoBauHuyenThoai-VN.apk, sau đó triển khai server do dự án kiểm soát theo giao thức có bằng chứng. Client web demo hiện tại không phải sản phẩm của mốc này.

## Sự thật đầu vào

- VN APK SHA-256: D61D4AE1994EC5BCAFDCFAF2406CC88ED9611CBB65DA853027799D50D6687EB4.
- APK có classes.dex, lib/*/libcocos2djs.so, assets/src/project.jsc, settings.jsc, jsb_polyfill.jsc và assets/project.manifest.
- Reference index ghi Cocos2d-x-lite v1.10.0, JSB, 36 product scenes, manifest version 1.0.0.02. Recovered jsb_polyfill.js trực tiếp đặt cc.ENGINE_VERSION = "1.10.3"; dùng runtime evidence này khi chọn tooling.
- APK không cung cấp mã nguồn server lịch sử. Đuôi .jsc/entropy cao không chứng minh bytecode; native có V8, jsb_set_xxtea_key và xxtea_decrypt. Cần truy loader để phân biệt JS mã hóa/nén với bytecode thực.
- Workspace chưa có project Cocos native có thể build; client/project.json chỉ là metadata.

## Phạm vi bắt buộc

1. Giữ APK gốc bất biến và lưu hash trước/sau mỗi run.
2. Unpack/decompile tĩnh vào work/apk-vn/<run-id>/; xuất file index, manifest, DEX report, native/JSC report và scene/resource map.
3. Xác định engine/toolchain từ binary thực tế trước khi chọn Cocos version.
4. Tạo client-recovered/ từ Android glue, JS/bytecode, scene/resource đã phục hồi; baseline giữ native .so prebuilt nếu cần và ghi rõ. Không tạo Cocos shell/scene mới để thay cho client phục hồi.
5. Ghi endpoint, method, field, opcode, nonce, auth và battle message chỉ khi có static proof hoặc trace runtime đã lọc.
6. Tạo server-compatible/ theo contract đã chứng minh; không lấy contract synthetic hiện tại làm giao thức APK.
7. So sánh screenshot/flow trên APK tham chiếu và client mới; nghiệm thu client trước server parity.

## Luồng nghiệm thu

APK VN → static inventory → engine/JSC/scene map → boot client gốc/repack → client-recovered build → network evidence → compatible server → client/server smoke.

Mốc đầu tiên: round-trip APK gốc và hiển thị scene của chính client đó trong lab. APK_REPACKED chỉ chứng minh đóng gói; ORIGINAL_CLIENT_BOOT cần screenshot/log; JSC_RECOVERED cần decoded output parse được; EDITABLE_CLIENT_BUILD cần build source chỉnh sửa được. Nếu JSC không phục hồi được, báo loader/offset/lỗi cụ thể; không tự chuyển sang viết lại client hoặc đổi engine.

## Ranh giới

- Chỉ xử lý APK do Owner cung cấp; không gọi provider endpoint lịch sử, không lấy secret/token người dùng, không phát hành lên store.
- Bản repack dùng debug key lab, không giả chữ ký gốc/không phát hành. Giữ package/JNI IDs cho baseline trên emulator disposable; đổi application ID chỉ sau khi map đủ các tham chiếu. Không cài đè bản người dùng.
- Tách bốn nhãn: SOURCE_RECOVERED, BEHAVIOR_REIMPLEMENTED, VISUAL_MATCHED, PROTOCOL_VERIFIED.
- Không dùng client/web, Canvas demo hoặc test server làm native acceptance.

## Tiêu chí hoàn thành

- work/apk-vn/<run-id>/ có evidence không chứa token/secret.
- client-recovered/ có lệnh build tái lập, APK output hash và log boot; phân biệt source đã khôi phục với native prebuilt.
- docs/reverse-engineering/vn-client-map.md liệt kê 36 product scenes, known/partial/unknown và evidence path.
- docs/protocol/vn-client-server-contract.md chỉ chứa message đã quan sát; phần chưa biết ghi UNKNOWN.
- server-compatible có smoke test qua client thật cho message đã chứng minh.

## Không thuộc mốc

Khôi phục mã nguồn server lịch sử không tồn tại trong APK, giả chữ ký/phân phối APK gốc, thanh toán/multiplayer mới hoặc thêm gameplay tự nghĩ ra để che thiếu evidence.

## Phạm vi static và runtime

Giải đóng gói/giải mã tài nguyên nội bộ bằng loader/thuật toán/key tìm được trong APK đã cung cấp là bước phân tích local của yêu cầu này. Không tạo thêm approval gate giấy. Giữ raw key local, không in key/token vào báo cáo. Tải tool hoặc chạy ngoài sandbox vẫn cần quyền môi trường tương ứng.

Runtime chỉ trên emulator/VM disposable, không tài khoản thật, chặn egress ở host/VM trước khi chạy. Endpoint/analytics/payment lịch sử không được gọi. Nếu lab chưa sẵn sàng thì vẫn tiếp tục phân tích static, không chuyển sang server demo.
