"""Prepare an opt-in, loopback-only bootstrap copy of the recovered client."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any


ORIGINAL_ASSIGNMENTS = "\n".join(
    (
        'a.url = "http://hzw-gosu-vi.miaomuxian.cn:20003";',
        'a.staticUrl = "http://hzw-gosu-vi.miaomuxian.cn:20001";',
        'a.gateHost = "hzw-gosu-vi.miaomuxian.cn";',
        'a.gatePort = "20100";',
    )
)
LAB_ASSIGNMENTS = "\n".join(
    (
        'a.url = "http://127.0.0.1:20003";',
        'a.staticUrl = "http://127.0.0.1:20001";',
        'a.gateHost = "127.0.0.1";',
        'a.gatePort = "20100";',
    )
)
# This deliberately matches one contiguous, exact assignment block.  It does
# not search/replace arbitrary endpoint-looking strings elsewhere in project.js.
BUILD_EXT_ASSIGNMENTS = re.compile(re.escape(ORIGINAL_ASSIGNMENTS))
PINNED_PROJECT_SHA256 = "9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818"
SDK_INIT_ANDROID_CALL = 'cc.sys.os == cc.sys.OS_ANDROID ? jsb.reflection.callStaticMethod("org/cocos2dx/javascript/SDKAdapter", "initPackageInfo", "()V") : cc.sys.os == cc.sys.OS_IOS && jsb.reflection.callStaticMethod("SDKAdapter", "initPackageInfo");'
SDK_INIT_ANDROID_LOCAL_CALL = 'if (cc.sys.os == cc.sys.OS_ANDROID) {\nd.sdkName = "mmx";\nd.channel = "Android";\n} else if (cc.sys.os == cc.sys.OS_IOS) {\njsb.reflection.callStaticMethod("SDKAdapter", "initPackageInfo");\n}'
LOCAL_AUTH_LOG_CALLS = (("console.log(t);", ""), ("console.log(e + \" \" + JSON.stringify(t));", ""))


def remap_build_ext_text(source: str) -> str:
    matches = list(BUILD_EXT_ASSIGNMENTS.finditer(source))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one buildExt assignment block, found {len(matches)}")
    return BUILD_EXT_ASSIGNMENTS.sub(LAB_ASSIGNMENTS, source, count=1)


def apply_local_auth_transform(source: str) -> str:
    """Replace the one pinned Android SDK init bridge call with local mmx fields."""
    count = source.count(SDK_INIT_ANDROID_CALL)
    if count != 1:
        raise ValueError(f"expected exactly one pinned sdkApi.init block, found {count}")
    transformed = source.replace(SDK_INIT_ANDROID_CALL, SDK_INIT_ANDROID_LOCAL_CALL, 1)
    for original, replacement in LOCAL_AUTH_LOG_CALLS:
        count = transformed.count(original)
        if count != 1:
            raise ValueError(f"expected exactly one HTTP log pin, found {count}")
        transformed = transformed.replace(original, replacement, 1)
    return transformed


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def remap_staged_source(staged_path: Path, reference_path: Path) -> str:
    """Verify a staged copy is pinned to the recovered source, then remap it."""
    if staged_path.resolve() == reference_path.resolve():
        raise ValueError("staged source and reference source must not be the same path")
    if staged_path.samefile(reference_path):
        raise ValueError("staged source and reference source must not be the same file")
    if _sha256(reference_path) != PINNED_PROJECT_SHA256:
        raise ValueError("reference source does not match pinned original")
    if _sha256(staged_path) != PINNED_PROJECT_SHA256:
        raise ValueError("staged source does not match pinned original")
    # Decode only after the byte-level pin check; unlike Path.read_text(), this
    # avoids universal-newline normalization elsewhere in the six-megabyte file.
    source = staged_path.read_bytes().decode("utf-8")
    transformed = remap_build_ext_text(source)
    transformed_bytes = transformed.encode("utf-8")
    staged_path.write_bytes(transformed_bytes)
    return hashlib.sha256(transformed_bytes).hexdigest()


def patch_local_auth_staged_source(staged_path: Path, reference_path: Path) -> str:
    """Apply local-auth only to a staged source produced by remap_staged_source."""
    if staged_path.resolve() == reference_path.resolve():
        raise ValueError("staged source and reference source must not be the same path")
    if staged_path.samefile(reference_path):
        raise ValueError("staged source and reference source must not be the same file")
    if _sha256(reference_path) != PINNED_PROJECT_SHA256:
        raise ValueError("reference source does not match pinned original")
    original = reference_path.read_bytes().decode("utf-8")
    expected = remap_build_ext_text(original).encode("utf-8")
    if staged_path.read_bytes() != expected:
        raise ValueError("staged source does not match expected remapped source")
    transformed = apply_local_auth_transform(expected.decode("utf-8"))
    staged_path.write_bytes(transformed.encode("utf-8"))
    return hashlib.sha256(transformed.encode("utf-8")).hexdigest()


def _manifest_payload(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise ValueError("manifest must not be a symlink")
    if not path.is_file():
        raise ValueError(f"manifest is missing: {path}")
    try:
        with path.open("rb") as manifest_file:
            raw = manifest_file.read(2 * 1024 * 1024 + 1)
        if len(raw) >= 2 * 1024 * 1024:
            raise ValueError("manifest exceeds 2 MiB")
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("manifest is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict) or not isinstance(value.get("assets"), dict):
        raise ValueError("manifest must be an object with assets")
    return value


def rewrite_manifest(manifest_path: Path, encoded_dir: Path, lab_manifest_path: Path) -> str:
    """Rewrite only local update metadata and the three encoded-JSC MD5s."""
    manifest = _manifest_payload(manifest_path)
    version = manifest.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError("manifest version is required")
    payload_names = ("settings.jsc", "jsb_polyfill.jsc", "project.jsc")
    for name in payload_names:
        if not (encoded_dir / name).is_file():
            raise ValueError(f"missing encoded payload: {name}")
    manifest["host"] = "127.0.0.1:20001"
    manifest["remoteVersionUrl"] = "http://127.0.0.1:20001/update/version.manifest"
    manifest["remoteManifestUrl"] = "http://127.0.0.1:20001/update/project.manifest"
    manifest["packageUrl"] = f"http://127.0.0.1:20001/update/{version}"
    for name in payload_names:
        key = f"src/{name}"
        entry = manifest["assets"].get(key)
        if not isinstance(entry, dict):
            raise ValueError(f"manifest is missing asset entry: {key}")
        entry["md5"] = hashlib.md5((encoded_dir / name).read_bytes()).hexdigest()
    encoded = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    manifest_path.write_bytes(encoded)
    lab_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    lab_manifest_path.write_bytes(encoded)
    return hashlib.sha256(encoded).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    remap = subparsers.add_parser("remap-source")
    remap.add_argument("--input", type=Path, required=True)
    remap.add_argument("--reference", type=Path, required=True)
    local = subparsers.add_parser("patch-local-auth")
    local.add_argument("--input", type=Path, required=True)
    local.add_argument("--reference", type=Path, required=True)
    rewrite = subparsers.add_parser("rewrite-manifest")
    rewrite.add_argument("--manifest", type=Path, required=True)
    rewrite.add_argument("--encoded-dir", type=Path, required=True)
    rewrite.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "remap-source":
            print(f"source_sha256={remap_staged_source(args.input, args.reference)}")
        elif args.command == "patch-local-auth":
            print(f"source_sha256={patch_local_auth_staged_source(args.input, args.reference)}")
        else:
            print(f"manifest_sha256={rewrite_manifest(args.manifest, args.encoded_dir, args.output)}")
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
