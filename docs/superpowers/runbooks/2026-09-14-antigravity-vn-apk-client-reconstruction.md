# Antigravity — Phục hồi client APK VN, không demo thay thế

[Spec](../specs/2026-09-14-vn-apk-client-reconstruction-design.md) · [Plan](../plans/2026-09-14-vn-apk-client-reconstruction.md) · [Output đã có](../../reverse-engineering/20260914T180000Z-vn-apk-static-report.md)

## Chỉ thị giao ngay

~~~text
Thực thi VN APK Client Reconstruction từ R1.
Baseline đã có tại work/apk-vn/20260914T180000Z: apktool, decoded, jadx và unsigned APK.
Không chạy lại decompiler nếu output/hash còn khớp.
Ưu tiên truy loader native và decode settings.jsc -> jsb_polyfill.jsc -> project.jsc.
Sau đó boot chính client gốc/repack trong lab, phục hồi client-recovered build được.
Không web demo, không Cocos shell/scene tự tạo, không server synthetic.
Server-compatible phải dựa trên request builder/response consumer và trace của client.
Nếu JSC chưa giải được: bàn giao offset/call-site/command/error, không tự đổi sang viết lại.
Không cần thêm vòng spec hoặc ký lại Gate0 cho static local đã giao.
~~~

## 1. Toolchain và baseline

Chạy từ workspace; dùng đường dẫn tuyệt đối vì adb/jadx/apktool chưa có trong PATH.

~~~powershell
Set-Location 'D:/GeminiWorkspaceNew/KhoBauHuyenThoai'
$apk = 'APK/KhoBauHuyenThoai-VN.apk'
$base = 'work/apk-vn/20260914T180000Z'
$sdk = 'C:/Users/tranm/AppData/Local/Android/Sdk'
$llvm = "$sdk/ndk/26.1.10909125/toolchains/llvm/prebuilt/windows-x86_64/bin"
Get-FileHash -Algorithm SHA256 $apk
java -jar tools/decompiler/apktool_3.0.3.jar --version
& tools/decompiler/jadx-1.5.6/bin/jadx.bat --version
& "$sdk/platform-tools/adb.exe" version
~~~

APK hash phải khớp D61D4AE1994EC5BCAFDCFAF2406CC88ED9611CBB65DA853027799D50D6687EB4.
Không thay JDK/SDK global. Thiếu quyền chạy executable thì xin đúng executable; mất PATH không nghĩa là thiếu SDK.

Dữ liệu có sẵn:
- apktool/: smali/assets/lib + raw manifest/resources cho round-trip.
- decoded/: AndroidManifest.xml/resources decoded + assets/lib.
- jadx/sources/:2.847 Java,7errors báo bởi CLI, cần đối chiếu smali.
- vn-baseline-unsigned.apk: APK_REPACKED; chưa ký/cài/boot.
- Android source đáng đọc trước: org/cocos2dx/javascript/AppActivity.java và SDKAdapter.java.

Ghi bước mới vào directory có timestamp thực và GUID, không --force vào baseline:
~~~powershell
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$suffix = [Guid]::NewGuid().ToString('N').Substring(0,8)
$runPath = "work/apk-vn/$stamp-$suffix"
if (Test-Path -LiteralPath $runPath) { throw 'Run path exists' }
New-Item -ItemType Directory -Path $runPath | Out-Null
~~~

## 2. Lệnh phân tích tiếp theo

~~~powershell
$native = "$base/decoded/lib/arm64-v8a/libcocos2djs.so"
& "$llvm/llvm-readelf.exe" --dyn-syms $native | Select-String 'xxtea|jsb_run_script|ScriptEngine|AppDelegate'
& "$llvm/llvm-objdump.exe" --disassemble --start-address=0x3eb5a8 --stop-address=0x3ebbb0 $native
Get-Content "$base/decoded/assets/main.js"
~~~

Trace AppDelegate → jsb_set_xxtea_key → file delegate → xxtea_decrypt/decompress → ScriptEngine. Resolve offset đúng ABI/hash; không dùng symbol address như file offset.

- Decode settings trước để lấy UUID/scenes/assets/launchScene.
- Decode polyfill để nhận diện engine/VM, project để lấy module gameplay/network.
- Nếu đầu ra text JS: parse, không execute trên host. Nếu bytecode: xác định VM version rồi disassemble.
- Decoder cần known-answer/wrong-key/truncated tests theo TDD; log mỗi bước hash/input/output/parser.
- Key nội bộ tìm trong APK dùng local để đọc tài nguyên; không in raw key/token/secret lên chat.
- Không có kết quả sau3attempt cùng hypothesis: đổi hướng phân tích/trace loader trong lab, báo offset cụ thể; không quay lại demo.

## 3. Boot chính client đó

R2 của plan: emulator/VM disposable không tài khoản, ABI phù hợp; chặn egress ở host/VM trước launch. Thiết bị đang nối ADB không mặc nhiên là emulator và không được cài đè.

Unsigned repack → zipalign → apksigner debug key lab → install trên lab mới → launch activity gốc → screenshot/logcat. Giữ package/JNI IDs cho baseline; đổi package có thể gãy provider/reflection/native và phải map trước.

Không clear log sau crash. Không dùng cài -r trên device có dữ liệu người dùng. Không giả chữ ký gốc. Nếu thiếu72assets/update path, lập missing list; không skip scene/asset giả để báo boot thành công.

Lab chưa có: tiếp tục R1/static scene map, không coi toàn dự án blocked. Không lập trình shell Cocos trống thay ORIGINAL_CLIENT_BOOT.

## 4. Project phục hồi và server

R3 tạo client-recovered từ source/resource/UUID graph đã đọc; prebuilt .so ghi rõ, không claim C++ recovered. Editor/VM phải khớp bằng chứng. Build scripts chỉ ghi sau khi toolchain được chọn và đã chạy, không đưa gradlew tưởng tượng thành command có sẵn.

R4 map request/response consumers, codec known-answer và source offsets. Gosu login bridge không đủ suy ra game protocol. Static-inferred khác runtime-confirmed. Không gọi server/analytics/payment cũ.

R5 xây bootstrap/login/player/gameplay theo từng message group đã map, smoke qua client phục hồi. Không copy /v1 synthetic. Không chờ toàn bộ giao thức mới làm nhóm đã xác minh.

## 5. Handoff mỗi run

~~~text
Input APK hash / run directory thực
Java/smali output và lỗi decompiler
Decoded settings/project/polyfill + SHA-256 + parser status
Hoặc JSC_BLOCKED: hàm/offset/input/command/error và hypothesis tiếp theo
APK_REPACKED khác ORIGINAL_CLIENT_BOOT khác EDITABLE_CLIENT_BUILD
Source recovered / native-prebuilt / unknown
Protocol static-inferred / runtime-confirmed / unknown
Build artifact, screenshot/logcat đã xem, missing assets
Exact next command
~~~

Không report số test server demo. Không tạo plan mỗi lỗi. Bảo toàn source/demo/evidence lịch sử; chỉ ngừng dùng demo như tiêu chí hoàn tất.
