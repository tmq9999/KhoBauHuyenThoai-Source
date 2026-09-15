# Run 20260914T180000Z — VN APK static decompile

Commands and exit codes:
- Apktool 3.0.3 decode --no-res → 0
- Apktool 3.0.3 resource decode → 0
- JADX 1.5.6 --show-bad-code --no-res → 1; 2,847 Java emitted, 7 errors reported by CLI; four files with explicit JADX ERROR markers found.
- Apktool 3.0.3 rebuild → 0; unsigned repack emitted
- aapt 34.0.0 dump badging → 0
- NDK llvm-readelf dyn-syms arm64 libcocos2djs.so → 0

Input APK SHA-256: D61D4AE1994EC5BCAFDCFAF2406CC88ED9611CBB65DA853027799D50D6687EB4
Outputs: work/apk-vn/20260914T180000Z/{apktool,decoded,jadx,vn-baseline-unsigned.apk}
Static report: docs/reverse-engineering/20260914T180000Z-vn-apk-static-report.md

The repacked APK is unsigned and has not been installed/run. JSC is not decoded; client source and server protocol are not yet recovered.
