# Phục hồi client APK Việt Nam — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development hoặc superpowers:executing-plans. Đọc spec, làm task có đầu ra; không dựng sản phẩm thay thế.

**Goal:** Decompile/phục hồi client APK VN, build và chạy chính client đó, sau đó viết server tương thích giao thức của nó.
**Architecture:** APK gốc bất biến. Baseline dùng smali/assets/native round-trip; source phục hồi lưu riêng trong client-recovered/. Server chỉ triển khai từng nhóm message có evidence.
**Tech Stack:** Java17, Apktool3.0.3, JADX1.5.6, Android build-tools34.0.0, NDK26.1.10909125. Cocos/V8 version phải xác định từ loader, không đoán từ tên APK.
**Spec:** [Client reconstruction](../specs/2026-09-14-vn-apk-client-reconstruction-design.md)
**Runbook:** [Antigravity](../runbooks/2026-09-14-antigravity-vn-apk-client-reconstruction.md)

## Global Constraints

- Root: D:/GeminiWorkspaceNew/KhoBauHuyenThoai.
- Input APK VN SHA-256: D61D4AE1994EC5BCAFDCFAF2406CC88ED9611CBB65DA853027799D50D6687EB4.
- Không demo web, không synthetic-v1, không Cocos shell hoặc scene mới thay cho client gốc.
- Không chuyển sang viết lại toàn bộ hoặc đổi engine nếu chưa hỏi người dùng.
- Native .so giữ prebuilt được cho baseline, nhưng không gọi là đã khôi phục C++.
- Không provider endpoints/tài khoản thật/payment; runtime chỉ lab disposable chặn egress.
- Không sửa APK gốc, không overwrite run lịch sử, không Git init/commit bắt buộc.
- Đầu ra decoded/raw giữ riêng với source working; mỗi biến đổi có hash và evidence.
- Không hứa source/visual/protocol giống100% khi chưa xác minh.

## Hiện trạng đã kiểm trực tiếp

[Report static](../../reverse-engineering/20260914T180000Z-vn-apk-static-report.md).

- [x] Tải và kiểm hash Apktool3.0.3/JADX1.5.6.
- [x] Apktool xuất5.316 smali, assets/native; decode XML/resources riêng, exit0.
- [x] JADX xuất2.847 Java; exit1 và7errors, cần đối chiếu smali.
- [x] Repack unsigned exit0: work/apk-vn/20260914T180000Z/vn-baseline-unsigned.apk.
- [ ] Chưa decode ba JSC, chưa ký/cài/boot bản repack, chưa có source gameplay/protocol.
- [ ] Chưa có lab disposable được xác minh. ADB có thiết bị kết nối nhưng chưa được phép coi là emulator; không cài lên đó.

## Đường găng và đầu ra

| Task | Việc làm | Đầu ra |
|---|---|---|
| R1 | Truy loader native và giải đóng gói JSC | settings/project/polyfill đọc được hoặc blocker tại offset cụ thể |
| R2 | Boot client gốc/repack trong lab | APK ký lab, screenshot/log scene thật |
| R3 | Phục hồi project chỉnh sửa/build | client-recovered/, UUID/resource/source map, build entry thật |
| R4 | Protocol từ code/consumer/trace | message table, codec, known-answer fixtures |
| R5 | Server tương thích từng nhóm | bootstrap/login/player/gameplay qua client phục hồi |
| R6 | Kiểm parity | screenshot/flow/protocol matrix, gaps |

**Bắt đầu R1 ngay, không chạy lại toàn bộ decompiler.** R1 native và scene-map có thể đọc song song. R2 chuẩn bị lab song song. R4 static bắt đầu ngay khi JSC đọc được; R5 theo nhóm message, không phải chờ toàn bộ protocol.

## R1 — Loader JSC: việc tiếp theo quan trọng nhất

**Read:** work/apk-vn/20260914T180000Z/decoded/assets/main.js; decoded/assets/src/*.jsc; decoded/lib/arm64-v8a/libcocos2djs.so; jadx/sources/org/cocos2dx/javascript/.
**Create:** docs/reverse-engineering/vn-loader-map.md; tools/apk-recovery/decode-jsc.py; tests/apk-recovery/test_decode_jsc.py; work/apk-vn/RUN_ID/recovered-js/.

- [ ] Chốt inventory7.083 ZIP entries (path, CRC, bytes, hash) và source→output mapping; kiểm APK trước/sau.
- [ ] Trace AppDelegate::applicationDidFinishLaunching → jsb_set_xxtea_key → file read delegate → xxtea_decrypt → decompress nếu có → ScriptEngine::evalString/runScript.
- [ ] Địa chỉ symbol ARM64 đã quan sát: AppDelegate0x3eb5a8; jsb_set_xxtea_key0x742dc0; runScript0x5185ac; evalString0x517eac; xxtea_decrypt0x11b7dbc. Là virtual address, không phải file offset. Re-resolve khi binary đổi.
- [ ] Tìm key/length/wrapper/byte-order ở call-site thực; giữ key nội bộ local, report chỉ fingerprint/offset. Không brute-force mù.
- [ ] Viết decoder sau khi xác định thuật toán; test RED với known-answer nhỏ tự tạo, corrupted length, wrong key, truncated payload; GREEN khi trả bytes đúng và từ chối input sai. Không chạy decoded script trên host.
- [ ] Decode settings.jsc trước để lấy rawAssets/scenes/launchScene/UUID; tiếp polyfill để xác minh engine/VM; cuối project.jsc.
- [ ] Đầu ra JS text: parse cú pháp không execute. Đầu ra gzip/zlib: xử lý theo loader, giữ intermediate bytes. Bytecode thực: xác định đúng VM version trước disassembler. Đuôi .jsc/entropy không đủ kết luận bytecode.
- [ ] Không formatter đè decoded output. Ghi hash blob, intermediate, decoded và parser result.
- [ ] Nếu thiếu static key/loader: ghi chính xác hàm/call-site còn thiếu; chuyển sang quan sát đầu vào ScriptEngine trong lab cô lập. Không chuyển sang dựng UI mới.

Lệnh tiếp theo có target thật:
~~~powershell
$llvm = 'C:/Users/tranm/AppData/Local/Android/Sdk/ndk/26.1.10909125/toolchains/llvm/prebuilt/windows-x86_64/bin'
$native = 'work/apk-vn/20260914T180000Z/decoded/lib/arm64-v8a/libcocos2djs.so'
& "$llvm/llvm-readelf.exe" --dyn-syms $native | Select-String 'xxtea|jsb_run_script|ScriptEngine|AppDelegate'
& "$llvm/llvm-objdump.exe" --disassemble --start-address=0x3eb5a8 --stop-address=0x3ebbb0 $native
~~~

**Đạt:** file decoded parse được + bằng chứng loader. **Chưa đạt:** JSC_BLOCKED có input/hash/offset/command/error, không ghi SOURCE_RECOVERED.

## R2 — Boot bản client gốc/repack; không client thay thế

**Create:** work/apk-vn/RUN_ID/lab/, artifacts/, capture/.

- [ ] Chuẩn bị emulator/VM mới không tài khoản, chặn egress từ host/VM trước khi chạy. Kiểm ABI: APK có x86/armv7/arm64, không x86_64; không giả định image hỗ trợ ABI khác.
- [ ] Dùng unsigned baseline đã có làm thử nghiệm; zipalign/apksigner bằng build-tools34.0.0 và debug keystore lab riêng. Không fake chữ ký gốc.
- [ ] Giữ package com.kbht.gg/activity/JNI IDs trong baseline lab. Không đổi application ID trước khi map provider/JNI/reflection.
- [ ] Không adb install -r trên thiết bị người dùng hoặc có dữ liệu thật. Chỉ dùng serial emulator/lab vừa tạo được xác minh.
- [ ] Bắt logcat trước launch; screenshot/frame boot và lỗi. Không clear log sau khi gặp crash.
- [ ] Kiểm loader main.js/SDKAdapter,50 search-path bundles và72 manifest paths thiếu nếu boot dừng. Xuất missing-resource list; không tự chế asset/bỏ scene để fake pass.
- [ ] Ghi signature-check/SDK-login/update blockers; không gọi Gosu/analytics/payment gốc. Chỉ remap endpoint sang lab sau khi contract tương ứng đã map.

**Đạt:** ORIGINAL_CLIENT_BOOT khi scene từ APK gốc hiển thị thật kèm log/screenshot. APK_REPACKED chỉ là đóng gói, không chứng minh boot/source recovery.

## R3 — Client project chỉnh sửa và rebuild được

**Create:** client-recovered/{android,assets,src,native-prebuilt,scripts}; resource-map.json; recovery-ledger.json.

- [ ] Từ settings/project/polyfill phục hồi, dựng graph UUID/import/raw-assets/scene và50 search paths; giữ đúng IDs, resource layout.
- [ ] Bảo toàn decoded source làm reference; bản chỉnh sửa nằm client-recovered/src. Không copy opaque JSC rồi gọi là source.
- [ ] Android glue dùng DEX/smali đã map; không compile cả output JADX mù vì Java decompile có lỗi và phụ thuộc SDK.
- [ ] Baseline cho phép native-prebuilt/.so; report native C++ chưa phục hồi. Chọn editor/VM theo bằng chứng, không gán Creator1.10.0 từ version string của engine.
- [ ] Tạo script build theo toolchain thực: JS/resource edit → đóng gói/align/sign → boot; command trong README phải đã chạy thành công.
- [ ] Phục hồi scene thật (boot/login trước, sau home/role/battle), font/localization/resources gốc trong lab; không tạo scene trống hoặc mock web.
- [ ] Lập36scene matrix known/partial/unknown;72missing assets phải có trạng thái, không asset giả.
- [ ] Đổi package hoặc engine chỉ sau phân tích và lựa chọn người dùng, không tự fallback clean-room rewrite.

**Đạt:** EDITABLE_CLIENT_BUILD khi nguồn đã recover chỉnh được, build và hiển thị thay đổi trong client thật. Liệt kê module recovered/prebuilt/unknown.

## R4 — Protocol từ chính client

**Create:** docs/protocol/vn-client-server-contract.md; protocol/vn/fixtures/; tests/protocol/.

- [ ] Trace request builders và response consumers trong project JS/bytecode; phân biệt Gosu SDK token callback với game handshake/session.
- [ ] Ghi transport HTTP/TCP/WebSocket, framing/opcode/path, endian, serializer, compression/encryption, auth, heartbeat, sequence/retry và error semantics.
- [ ] Mỗi field có file+line hoặc native offset hoặc sanitized trace. Không đoán response chỉ từ tên hàm/URL.
- [ ] Static-inferred và runtime-confirmed tách nhãn. Endpoint cũ chết: tạo local fixtures theo consumer fields, ghi inferred; không giả backend lịch sử đã khôi phục.
- [ ] Codec TDD: decode fixture bytes ra expected literal fields; encode lại expected bytes; malformed/truncated/oversized reject. Không tính expected bằng chính decoder đang test.
- [ ] Không dùng /v1 hoặc synthetic-v1 hiện có nếu thiếu evidence; không in token/credential vào trace report.

**Đạt:** nhóm bootstrap/login/player đủ field để kiểm client thật. UNKNOWN không ngăn làm nhóm đã chứng minh, nhưng không được coi compatible.

## R5 — Server tương thích tăng dần

**Create:** server-compatible/ dùng codec R4, contract tests và lab fixtures.

- [ ] S1 version/bootstrap/resource metadata theo yêu cầu client.
- [ ] S2 auth lab/server list/session/player; không truy cập tài khoản/provider cũ.
- [ ] S3 home/role/bag/config theo client data đã xác minh.
- [ ] S4 request/result/reward battle đúng format/field/nonce. Luật phía server không nằm trong APK phải ghi inferred, không tự nhận100%.
- [ ] Mỗi nhóm: fixture RED → handler → client real smoke → GREEN; endpoint test không thay client smoke.
- [ ] Durable DB/Redis tests riêng; không bắt Docker trước task decompiler. Không migrate DB người dùng.

## R6 — Nghiệm thu

**Create:** docs/release/RUN_ID-native-client-acceptance.md.

- [ ] Input/output APK hashes, unsigned/signed, tool/VM/device/API/ABI, keystore public fingerprint.
- [ ] Client thật: boot → login lab → home → gameplay đã map; screenshot/video/log được lọc.
- [ ] 36scene/flow/protocol matrix, missing assets/unknowns. Pixel diff/SSIM kèm viewport và mask vùng động; không một con số tự thay nghiệm thu.
- [ ] Build command client-recovered và start command server-compatible có thật, chạy lại được.
- [ ] Nhãn riêng: ANDROID_DECOMPILED, JSC_RECOVERED, APK_REPACKED, ORIGINAL_CLIENT_BOOT, EDITABLE_CLIENT_BUILD, PROTOCOL_VERIFIED, SERVER_COMPATIBLE.

## Hạn chế lãng phí thời gian/quota

Không test/review demo web trong plan này. Không tạo spec/plan mới mỗi checkpoint. Một người phân tích mỗi binary; chỉ song song native/scene-map nếu độc lập. Decoder lỗi3attempt cùng giả thuyết phải ghi blocker/đổi hypothesis, không lặp review vô hạn. Không hứa ETA100% trước khi biết project.jsc decode được đến đâu.
