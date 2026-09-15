
# VN APK static decompile report — run 20260914T180000Z

## Commands actually run

| Command | Exit | Evidence |
|---|---:|---|
| java -jar tools/decompiler/apktool_3.0.3.jar d --force --no-res APK/KhoBauHuyenThoai-VN.apk -o work/apk-vn/20260914T180000Z/apktool | 0 | Unpacked assets, smali, manifest and native libraries |
| java -jar tools/decompiler/apktool_3.0.3.jar d APK/KhoBauHuyenThoai-VN.apk -o work/apk-vn/20260914T180000Z/decoded | 0 | Decoded resources and manifest |
| tools/decompiler/jadx-1.5.6/bin/jadx.bat --show-bad-code --no-res -d work/apk-vn/20260914T180000Z/jadx APK/KhoBauHuyenThoai-VN.apk | 1 | 2,847 Java files emitted; 7 errors reported; markers found in four Google/ZXing files, all 7 not yet classified |
| java -jar tools/decompiler/apktool_3.0.3.jar b work/apk-vn/20260914T180000Z/apktool -o work/apk-vn/20260914T180000Z/vn-baseline-unsigned.apk | 0 | Repacked unsigned APK produced |

## APK identity

- Input SHA-256: D61D4AE1994EC5BCAFDCFAF2406CC88ED9611CBB65DA853027799D50D6687EB4.
- Package com.kbht.gg, versionName 1.0.0, versionCode 5.
- Launch activity org.cocos2dx.javascript.AppActivity.
- min SDK 16, target SDK 26; native ABIs arm64-v8a, armeabi-v7a and x86.
- Apktool 3.0.3 SHA-256: dbf930b076c6b9be08d57c449cacefc3bdd6b71ebd59b3066fc0e1f5b14f9423.
- JADX 1.5.6 SHA-256: 545ea2be9c242511bc145755cf4bda2485ade42966e096f8b4d3da2a230e8974.
- Repacked unsigned artifact SHA-256: 27396bf9e9b36086535ac25e5411b4d9fba0e0217c66ae9eeab042e1bc0f0978 (100,541,235 bytes). This proves a static round-trip, not a runnable rebuild or source recovery.

## JSC and native evidence

| Path | Bytes | SHA-256 | First 16 bytes | Entropy |
|---|---:|---|---|---:|
| assets/src/project.jsc | 899,596 | c8e81942674e02aa042d35b95feadb28588f9468d1fbcbe86f6b6fc4efeeb0a1 | 48cb619f36699d9ea245943211d1321a | 7.9998 |
| assets/src/settings.jsc | 106,260 | 11e4b984a17b9c2b8a2ea054c2c16ebfd140e7fbfc23020e9aef4c31a0be8fd1 | 7ff4d75e41260f18d9ea752b54336921 | 7.9986 |
| assets/src/jsb_polyfill.jsc | 134,652 | 6119d0112965b2d921014e2f5161845488d06d37fc155807cfdd5862e28d45a9 | 20700e26cc0778931fc27ac612dabfbc | 7.9986 |

All three blobs have no known ZIP/ELF magic and near-uniform byte distribution. This is evidence for a packed/encrypted candidate only; it does not prove encryption or identify the VM format. assets/main.js loads src/settings.js and src/jsb_polyfill.js in the native window.jsb branch; settings selects src/project.js and the Cocos asset library/launch scene. assets/assetsx/paths.json contains 50 hashed subpackage directories used as additional JSB search paths.

Native libcocos2djs.so sizes are arm64 27,268,312 bytes, armv7 19,116,708 and x86 29,117,480. Dynamic symbols include jsb_run_script, jsb_register_all_modules, jsb_set_xxtea_key, xxtea_decrypt, xxtea_encrypt, se::ScriptEngine::runScript, se::ScriptEngine::evalString and AppDelegate::applicationDidFinishLaunching; V8 symbols are present. Recovered jsb_polyfill.js contains cc.ENGINE_VERSION = "1.10.3". The loader/key path is proven in work/apk-vn/20260914T135911Z-efc5da6a/loader-analysis.md.

## What is and is not recovered

- Android Java/Smali framework and boot path are available under work/apk-vn/20260914T180000Z/jadx and work/apk-vn/20260914T180000Z/apktool.
- The three bootstrap JSC payloads are recovered as gzip-wrapped JavaScript; gameplay semantics are readable in project.js but still require scene/consumer mapping.
- No endpoint or server schema is proven by this run. The synthetic-v1 API is unrelated and must not enter compatibility contracts.
- Next deliverable: identify original JSC loader/decoded output and boot the original/repacked client in a network-isolated lab. Empty/new replacement scenes are not client recovery.
