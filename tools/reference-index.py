"""Read-only APK reference indexer; Python 3.12 standard library."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import struct
import sys
import tempfile
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path

MIB = 1024 * 1024
REGISTRY = {
    "vn": (
        "KhoBauHuyenThoai-VN.apk",
        "d61d4ae1994ec5bcafdcfaf2406cc88ed9611cbb65da853027799d50d6687eb4",
        100972543, 7083, 177372336, 6462, "1.0.0.02", 6454, 37, 36, 72,
        (3558, 1455, 658, 493, 248, 0, 3, 43, 4),
    ),
    "sp-comparator": (
        "sp-071023.apk",
        "b69427af63e668364a20c64c3a9d9440e498f9e88c15ddbe233fe5929edaf14b",
        208003536, 15795, 262567007, 14341, "1.0.0.38", 14335, 41, 41, 0,
        (8789, 2972, 1084, 713, 384, 386, 5, 3, 5),
    ),
}
EXTENSIONS = ("json", "png", "jpg", "mp3", "atlas", "bin", "jsc", "js", "other")


class IndexerError(Exception):
    def __init__(self, code, artifact_id=None):
        super().__init__(code)
        self.code = code
        self.artifact_id = artifact_id if artifact_id in REGISTRY else None


def require(condition, code="ZIP_UNSAFE"):
    if not condition:
        raise IndexerError(code)


@dataclass(frozen=True)
class Limits:
    input_bytes: int = 256 * MIB
    entries: int = 25000
    directory_bytes: int = 16 * MIB
    total_bytes: int = 512 * MIB
    member_bytes: int = 64 * MIB
    metadata_bytes: int = 8 * MIB
    chunk_bytes: int = MIB
    ratio: int = 1000
    json_depth: int = 128


@dataclass(frozen=True, repr=False)
class ReferenceScan:
    metadata: dict
    product_scene_keys: frozenset[str]


def safe_name(name):
    require(isinstance(name, str) and bool(name))
    require(not any(c in name for c in ("\x00", "\\", ":")))
    parts = name[:-1].split("/") if name.endswith("/") else name.split("/")
    require(all(part not in ("", ".", "..") for part in parts))
    return "/".join(parts).casefold()


def local_path(value, root=None):
    raw = str(value)
    require(not raw.startswith(("//", "\\\\")), "PATH_NOT_ALLOWED")
    require(".." not in re.split(r"[\\/]", raw), "PATH_NOT_ALLOWED")
    p = Path(value)
    if root is not None and not p.is_absolute():
        p = root / p
    require(p.is_absolute(), "PATH_NOT_ALLOWED")
    for item in reversed((p, *p.parents)):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        require(not stat.S_ISLNK(info.st_mode), "PATH_NOT_ALLOWED")
        require(not getattr(info, "st_file_attributes", 0) & 0x400, "PATH_NOT_ALLOWED")
    resolved = p.resolve()
    if root is not None:
        require(resolved.is_relative_to(root), "PATH_NOT_ALLOWED")
    return resolved


def exact_read(fp, size):
    data = fp.read(size)
    require(len(data) == size, "ZIP_INVALID")
    return data


def reject_zip64_extra(data):
    pos = 0
    while pos < len(data):
        require(pos + 4 <= len(data), "ZIP_INVALID")
        kind, size = struct.unpack_from("<HH", data, pos)
        pos += 4
        require(kind != 1 and pos + size <= len(data))
        pos += size


def directory_layout(fp, limits):
    fp.seek(0, 2)
    size = fp.tell()
    require(22 <= size <= limits.input_bytes)
    fp.seek(max(0, size - 65557))
    tail = fp.read(65557)
    end = len(tail)
    found = None
    while end > 0:
        pos = tail.rfind(b"PK\x05\x06", 0, end)
        if pos < 0:
            break
        if pos + 22 <= len(tail):
            fields = struct.unpack_from("<4s4H2IH", tail, pos)
            if pos + 22 + fields[7] == len(tail):
                found = (size - len(tail) + pos, fields)
                break
        end = pos
    require(found is not None, "ZIP_INVALID")
    eocd, fields = found
    _, disk, cd_disk, on_disk, count, cd_size, cd_start, _ = fields
    require(disk == cd_disk == 0 and on_disk == count)
    require(count < 65535 and count <= limits.entries)
    require(cd_size <= limits.directory_bytes)
    require(cd_start + cd_size == eocd, "ZIP_INVALID")
    fp.seek(cd_start)
    directory = exact_read(fp, cd_size)
    records, aliases, pos, total = [], set(), 0, 0
    for _ in range(count):
        require(pos + 46 <= len(directory), "ZIP_INVALID")
        row = struct.unpack_from("<4s6H3I5H2I", directory, pos)
        require(row[0] == b"PK\x01\x02", "ZIP_INVALID")
        flags, method, crc, compressed, plain = row[3], row[4], row[7], row[8], row[9]
        name_n, extra_n, comment_n, disk_n, attrs, offset = row[10], row[11], row[12], row[13], row[15], row[16]
        stop = pos + 46 + name_n + extra_n + comment_n
        require(stop <= len(directory), "ZIP_INVALID")
        raw_name = directory[pos + 46:pos + 46 + name_n]
        require(b"\x00" not in raw_name)
        name = raw_name.decode("utf-8" if flags & 0x800 else "cp437", "strict")
        alias = safe_name(name)
        require(alias not in aliases)
        aliases.add(alias)
        reject_zip64_extra(directory[pos + 46 + name_n:pos + 46 + name_n + extra_n])
        mode = stat.S_IFMT(attrs >> 16)
        require(mode in (0, stat.S_IFREG, stat.S_IFDIR) and disk_n == 0)
        require(not flags & 0x41 and method in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED))
        require(plain <= limits.member_bytes and compressed < 0xFFFFFFFF and offset < cd_start)
        require(plain == 0 or (compressed > 0 and plain <= compressed * limits.ratio))
        if name.endswith("/"):
            require(plain == 0)
        total += plain
        require(total <= limits.total_bytes)
        records.append((offset, raw_name, flags, method, crc, compressed, plain))
        pos = stop
    require(pos == len(directory), "ZIP_INVALID")
    return cd_start, records


def validate_zip(fp, limits=Limits()):
    """Validate raw directory/local headers and bounded CRC; restore cursor."""
    initial = fp.tell()
    try:
        require(0 < limits.chunk_bytes <= MIB)
        cd_start, records = directory_layout(fp, limits)
        spans, total = [], 0
        for offset, raw_name, flags, method, crc, compressed, plain in records:
            fp.seek(offset)
            row = struct.unpack("<4s5H3I2H", exact_read(fp, 30))
            require(row[0] == b"PK\x03\x04", "ZIP_INVALID")
            require(row[2] == flags and row[3] == method, "ZIP_INVALID")
            name = exact_read(fp, row[9])
            require(name == raw_name and b"\x00" not in name, "ZIP_INVALID")
            reject_zip64_extra(exact_read(fp, row[10]))
            start = fp.tell()
            stop = start + compressed
            require(stop <= cd_start, "ZIP_INVALID")
            if not flags & 8:
                require((row[6], row[7], row[8]) == (crc, compressed, plain), "ZIP_INVALID")
            else:
                fp.seek(stop)
                descriptor = exact_read(fp, 4)
                if descriptor == b"PK\x07\x08":
                    descriptor = exact_read(fp, 12)
                    stop += 16
                else:
                    descriptor += exact_read(fp, 8)
                    stop += 12
                require(struct.unpack("<III", descriptor) == (crc, compressed, plain), "ZIP_INVALID")
            require(stop <= cd_start, "ZIP_INVALID")
            spans.append((offset, stop, start, method, crc, compressed, plain))
        spans.sort()
        for previous, current in zip(spans, spans[1:]):
            require(previous[1] <= current[0], "ZIP_INVALID")
        for _, _, start, method, crc, compressed, plain in spans:
            fp.seek(start)
            remaining, emitted, actual_crc = compressed, 0, 0
            inflater = zlib.decompressobj(-15) if method == zipfile.ZIP_DEFLATED else None
            while remaining:
                data = exact_read(fp, min(remaining, limits.chunk_bytes))
                remaining -= len(data)
                while data:
                    previous_n = len(data)
                    if inflater is None:
                        block, data = data, b""
                    else:
                        block = inflater.decompress(data, limits.chunk_bytes)
                        data = inflater.unconsumed_tail
                        require(not inflater.unused_data, "ZIP_INVALID")
                    emitted += len(block)
                    total += len(block)
                    require(emitted <= plain and emitted <= limits.member_bytes)
                    require(total <= limits.total_bytes)
                    actual_crc = zlib.crc32(block, actual_crc)
                    require(block or len(data) < previous_n, "ZIP_INVALID")
            if inflater is not None:
                require(inflater.eof and not inflater.unused_data, "ZIP_INVALID")
            require(emitted == plain, "ZIP_INVALID")
            require(actual_crc == crc, "ZIP_CRC_FAILED")
    except (UnicodeError, struct.error, zlib.error, zipfile.BadZipFile):
        raise IndexerError("ZIP_INVALID") from None
    finally:
        fp.seek(initial)


def json_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "REFERENCE_METADATA_UNEXPECTED")
        result[key] = value
    return result


def read_json(zf, name, limits, used):
    try:
        info = zf.getinfo(name)
        require(info.file_size <= limits.metadata_bytes, "REFERENCE_METADATA_UNEXPECTED")
        chunks, size = [], 0
        with zf.open(info) as source:
            while block := source.read(limits.chunk_bytes):
                size += len(block)
                used[0] += len(block)
                require(size <= limits.metadata_bytes and used[0] <= limits.total_bytes, "REFERENCE_METADATA_UNEXPECTED")
                chunks.append(block)
        text = b"".join(chunks).decode("utf-8", "strict")
        quoted = escaped = False
        depth = 0
        for char in text:
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
            elif char in "[{":
                depth += 1
                require(depth <= limits.json_depth, "REFERENCE_METADATA_UNEXPECTED")
            elif char in "]}":
                depth -= 1
        def invalid_constant(_):
            raise IndexerError("REFERENCE_METADATA_UNEXPECTED")
        return json.loads(text, object_pairs_hook=json_object, parse_constant=invalid_constant)
    except (KeyError, UnicodeError, ValueError, RecursionError, zipfile.BadZipFile):
        raise IndexerError("REFERENCE_METADATA_UNEXPECTED") from None


def inspect_metadata(zf, artifact_id, limits=Limits()):
    """Caller must run validate_zip first; synthetic tests may use this seam."""
    require(artifact_id in REGISTRY, "ARGUMENT_INVALID")
    infos = zf.infolist()
    names = {i.filename for i in infos}
    used, scenes = [0], set()
    manifest = read_json(zf, "assets/project.manifest", limits, used)
    require(type(manifest) is dict and type(manifest.get("assets")) is dict, "REFERENCE_METADATA_UNEXPECTED")
    version = manifest.get("version")
    require(type(version) is str and re.fullmatch(r"[0-9]{1,4}(?:\.[0-9]{1,4}){1,5}", version), "REFERENCE_METADATA_UNEXPECTED")
    shards = []
    if artifact_id == "vn":
        shards = read_json(zf, "assets/assetsx/paths.json", limits, used)
        require(type(shards) is list and len(shards) <= limits.entries, "REFERENCE_METADATA_UNEXPECTED")
        require(all(type(s) is str and re.fullmatch(r"[0-9a-f]{32}", s) for s in shards), "REFERENCE_METADATA_UNEXPECTED")
        require(len(shards) == len(set(shards)), "REFERENCE_METADATA_UNEXPECTED")
        for name in sorted(names):
            if not re.fullmatch(r"assets/assetsx/[0-9a-f]{32}/res/import/[0-9a-f]{2}/[^/]+\.json", name):
                continue
            stack = [read_json(zf, name, limits, used)]
            while stack:
                value = stack.pop()
                if type(value) is dict:
                    if value.get("__type__") == "cc.SceneAsset":
                        scene = value.get("_name")
                        require(type(scene) is str and re.fullmatch(r"[A-Za-z0-9_]{1,100}", scene), "REFERENCE_METADATA_UNEXPECTED")
                        require(scene not in scenes, "REFERENCE_METADATA_UNEXPECTED")
                        scenes.add(scene)
                    stack.extend(value.values())
                elif type(value) is list:
                    stack.extend(value)
    else:
        config = read_json(zf, "assets/assets/main/config.json", limits, used)
        require(type(config) is dict and type(config.get("scenes")) is dict, "REFERENCE_METADATA_UNEXPECTED")
        for key in config["scenes"]:
            match = re.fullmatch(r"db://assets/ui/([A-Za-z0-9_]{1,100})\.fire", key)
            require(match is not None, "REFERENCE_METADATA_UNEXPECTED")
            scenes.add(match[1])
    missing = ambiguous = 0
    for logical in manifest["assets"]:
        safe_name(logical)
        candidates = ["assets/" + logical]
        candidates.extend("assets/assetsx/" + shard + "/" + logical for shard in shards)
        count = sum(candidate in names for candidate in candidates)
        missing += count == 0
        ambiguous += count > 1
    extension_counts = dict.fromkeys(EXTENSIONS, 0)
    asset_count = 0
    for info in infos:
        if info.filename.startswith("assets/") and not info.is_dir():
            extension = Path(info.filename).suffix[1:].lower()
            extension_counts[extension if extension in extension_counts else "other"] += 1
            asset_count += 1
    products = frozenset(scenes - {"test"})
    metadata = {
        "id": artifact_id, "fileName": REGISTRY[artifact_id][0],
        "sha256": None, "sizeBytes": None,
        "zipEntries": len(infos),
        "uncompressedBytes": sum(i.file_size for i in infos),
        "assetFileCount": asset_count, "crcFirstBadEntry": None,
        "manifestVersion": version, "manifestAssetCount": len(manifest["assets"]),
        "assetExtensionCounts": extension_counts,
        "sceneCounts": {"allSerialized": len(scenes), "product": len(products)},
        "manifestCoverage": {
            "missingPaths": missing, "ambiguousPaths": ambiguous,
            "checksumStatus": "not-evaluated",
        },
    }
    return ReferenceScan(metadata, products)


def digest(fp):
    fp.seek(0)
    value = hashlib.sha256()
    while block := fp.read(MIB):
        value.update(block)
    return value.hexdigest()


def identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def index_reference_apk(root, artifact_id):
    require(artifact_id in REGISTRY, "ARGUMENT_INVALID")
    root = local_path(root)
    path = local_path(root / "APK" / REGISTRY[artifact_id][0], root)
    try:
        with path.open("rb") as fp:
            before = os.fstat(fp.fileno())
            require(before.st_size <= Limits().input_bytes)
            actual_hash = digest(fp)
            require(actual_hash == REGISTRY[artifact_id][1], "REFERENCE_HASH_MISMATCH")
            validate_zip(fp)
            fp.seek(0)
            with zipfile.ZipFile(fp) as zf:
                scan = inspect_metadata(zf, artifact_id)
            require(identity(before) == identity(os.fstat(fp.fileno())), "REFERENCE_CHANGED")
            require(identity(before) == identity(path.stat()), "REFERENCE_CHANGED")
            require(digest(fp) == actual_hash, "REFERENCE_CHANGED")
            scan.metadata.update(sha256=actual_hash, sizeBytes=before.st_size)
            return scan
    except IndexerError as error:
        raise IndexerError(error.code, artifact_id) from None
    except (OSError, zipfile.BadZipFile):
        raise IndexerError("INPUT_IO_FAILED", artifact_id) from None


def build_summary(vn, sp):
    return {
        "schemaVersion": 1, "generatedBy": "reference-index.py",
        "referenceArtifacts": [dict(vn.metadata), dict(sp.metadata)],
        "comparison": {"sharedProductSceneCount": len(vn.product_scene_keys & sp.product_scene_keys)},
    }


def expected_summary():
    artifacts = []
    for artifact_id, row in REGISTRY.items():
        filename, sha, size, entries, unpacked, assets, version, records, all_scenes, product, missing, extensions = row
        artifacts.append({
            "id": artifact_id, "fileName": filename, "sha256": sha,
            "sizeBytes": size, "zipEntries": entries, "uncompressedBytes": unpacked,
            "assetFileCount": assets, "crcFirstBadEntry": None,
            "manifestVersion": version, "manifestAssetCount": records,
            "assetExtensionCounts": dict(zip(EXTENSIONS, extensions)),
            "sceneCounts": {"allSerialized": all_scenes, "product": product},
            "manifestCoverage": {"missingPaths": missing, "ambiguousPaths": 0, "checksumStatus": "not-evaluated"},
        })
    return {
        "schemaVersion": 1, "generatedBy": "reference-index.py",
        "referenceArtifacts": artifacts,
        "comparison": {"sharedProductSceneCount": 36},
    }


def same_shape_and_values(actual, expected):
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return actual.keys() == expected.keys() and all(same_shape_and_values(actual[k], v) for k, v in expected.items())
    if type(expected) is list:
        return len(actual) == len(expected) and all(same_shape_and_values(a, b) for a, b in zip(actual, expected))
    return actual == expected


def encode_summary(summary):
    require(same_shape_and_values(summary, expected_summary()), "OUTPUT_SCHEMA_INVALID")
    payload = (json.dumps(summary, ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
    require(len(payload) <= 256 * 1024, "OUTPUT_SCHEMA_INVALID")
    return payload


def write_summary(root, output, payload):
    root = local_path(root)
    path = local_path(output, root)
    allowed = local_path(root / "tools" / "fixtures", root)
    require(path.is_relative_to(allowed) and path.suffix == ".json", "PATH_NOT_ALLOWED")
    require(path.parent.is_dir(), "PATH_NOT_ALLOWED")
    require(type(payload) is bytes and len(payload) <= 256 * 1024, "OUTPUT_SCHEMA_INVALID")
    try:
        require(encode_summary(json.loads(payload)) == payload, "OUTPUT_SCHEMA_INVALID")
    except (ValueError, UnicodeError):
        raise IndexerError("OUTPUT_SCHEMA_INVALID") from None
    temp = None
    try:
        if path.exists():
            require(path.is_file() and path.stat().st_size <= 256 * 1024, "OUTPUT_EXISTS")
            require(path.read_bytes() == payload, "OUTPUT_EXISTS")
            return
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".reference-", delete=False) as stream:
            temp = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if os.name == "nt":
            os.rename(temp, path)
        else:
            os.link(temp, path)
    except FileExistsError:
        raise IndexerError("OUTPUT_EXISTS") from None
    except OSError:
        raise IndexerError("OUTPUT_IO_FAILED") from None
    finally:
        if temp is not None and temp.exists():
            temp.unlink()


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise IndexerError("ARGUMENT_INVALID")


def main(argv=None):
    try:
        parser = ArgumentParser(description="Index the two pinned local APK references.")
        parser.add_argument("--root", required=True)
        parser.add_argument("--output", required=True)
        args = parser.parse_args(argv)
        root = local_path(args.root)
        require(root == Path(__file__).resolve().parents[1], "PATH_NOT_ALLOWED")
        vn = index_reference_apk(root, "vn")
        sp = index_reference_apk(root, "sp-comparator")
        summary = build_summary(vn, sp)
        payload = encode_summary(summary)
        write_summary(root, Path(args.output), payload)
        print('{"status":"ok"}')
        return 0
    except IndexerError as error:
        result = {"code": error.code}
        if error.artifact_id:
            result["artifactId"] = error.artifact_id
        print(json.dumps({"error": result}, separators=(",", ":")), file=sys.stderr)
        code = error.code
        if code in ("ARGUMENT_INVALID", "PATH_NOT_ALLOWED"):
            return 2
        if code.startswith("REFERENCE_HASH") or code == "REFERENCE_CHANGED":
            return 3
        if code.startswith("ZIP_"):
            return 4
        if code in ("REFERENCE_METADATA_UNEXPECTED", "OUTPUT_SCHEMA_INVALID"):
            return 5
        if code.startswith("OUTPUT_"):
            return 6
        return 7


if __name__ == "__main__":
    raise SystemExit(main())
