# VN APK loader map — run 20260914T180000Z

Trạng thái: static evidence; ba bootstrap JSC đã giải được; gameplay/protocol vẫn đang map.

## Luồng đã quan sát

AppActivity extends Cocos2dxActivity và tạo Cocos2dxGLSurfaceView. assets/main.js có nhánh window.jsb nạp src/settings.js và src/jsb_polyfill.js; boot đọc settings.jsList/project.js, AssetLibrary và launchScene. assets/assetsx/paths.json thêm 50 đường tìm kiếm bundle.

## File thật để đọc tiếp

- [AppActivity.java](../../work/apk-vn/20260914T180000Z/jadx/sources/org/cocos2dx/javascript/AppActivity.java)
- [SDKAdapter.java](../../work/apk-vn/20260914T180000Z/jadx/sources/org/cocos2dx/javascript/SDKAdapter.java)
- [main.js](../../work/apk-vn/20260914T180000Z/decoded/assets/main.js)
- [Manifest XML](../../work/apk-vn/20260914T180000Z/decoded/AndroidManifest.xml)

SDKAdapter gọi sdkApi.verifyToken thông qua Cocos2dxJavascriptJavaBridge; đây là Gosu SDK bridge, không đủ suy ra giao thức game server.

## Native/JSC cần giải tiếp

libcocos2djs.so chứa V8, se::ScriptEngine, jsb_set_xxtea_key, xxtea_decrypt/encrypt. `jsb_polyfill.js` sau giải có `cc.ENGINE_VERSION = "1.10.3"`.

Địa chỉ loader ARM64 đã được xác minh trong `work/apk-vn/20260914T135911Z-efc5da6a/loader-analysis.md`: AppDelegate key setup `0x3eb610–0x3eb628`, active runScript delegate `0x7404f4`, XXTEA callsite `0x7405d0 → xxtea_decrypt 0x11b7dbc`, gzip test `0x7405e0`, inflate callsite `0x7405f8 → inflateMemory 0x116508c`. Các địa chỉ này là virtual/file offsets của binary hiện tại; phải resolve lại nếu binary đổi.

Ba file có entropy cao nhưng loader đã xác minh: mỗi blob giải XXTEA thành gzip (`1f8b`), sau đó inflate thành JavaScript UTF-8. `settings.jsc` → `settings.decoded` 237,138 bytes, `jsb_polyfill.jsc` → 549,023 bytes, `project.jsc` → 6,039,275 bytes; cả ba `node --check` đạt mà không execute. Đây đủ điều kiện `JSC_RECOVERED` cho ba bootstrap blobs; gameplay semantics và protocol vẫn cần phân tích consumer.

APK_REPACKED đã có và bản tái mã hóa từ client-recovered/src đã ký debug; chưa installed/boot. JavaScript gameplay đã đọc được, protocol Pomelo có báo cáo static nhưng chưa xác minh runtime. Không Cocos shell/scene mới thay cho kết quả phục hồi.
