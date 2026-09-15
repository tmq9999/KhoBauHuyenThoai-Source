"""Narrow, bounded XXTEA decoder for the VN APK's JSC assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import zlib

DELTA = 0x9E3779B9
MASK = 0xFFFFFFFF
MAX_OUTPUT = 32 * 1024 * 1024
MAX_CIPHERTEXT = MAX_OUTPUT + 4
VN_NATIVE_SIZE = 27268312
_IO_CHUNK = 1024 * 1024
VN_NATIVE_SHA256 = "e348349e9c7ab476463092eee1f398eb360e37a74f9d96bf987ba43e164558d3"
VN_KEY_OFFSET = 0x13AA750
VN_KEY_SHA256 = "2e7565b3399fa9f1859d734431062ccc228b597383ca8347151d67df851960a3"
ROOT = Path(__file__).resolve().parents[2]


def _words(data: bytes) -> list[int]:
    return list(struct.unpack("<%dI" % (len(data) // 4), data))


def _normalize_key(key: bytes) -> list[int]:
    if not isinstance(key, (bytes, bytearray)):
        raise TypeError("key must be bytes")
    return _words(bytes(key)[:16].ljust(16, b"\0"))


def xxtea_decrypt(data: bytes, key: bytes) -> bytes:
    """Decrypt Cocos' include-length XXTEA byte representation."""
    if len(data) < 8 or len(data) % 4:
        raise ValueError("ciphertext must be at least 8 bytes and 4-byte aligned")
    if len(data) > MAX_CIPHERTEXT:
        raise ValueError("ciphertext exceeds limit")
    v = _words(data)
    n = len(v)
    k = _normalize_key(key)
    q = 6 + 52 // n
    total = (q * DELTA) & MASK
    y = v[0]
    while total:
        e = (total >> 2) & 3
        for p in range(n - 1, 0, -1):
            z = v[p - 1]
            mx = ((((z >> 5) ^ (y << 2)) + ((y >> 3) ^ (z << 4))) ^
                  ((total ^ y) + (k[(p & 3) ^ e] ^ z))) & MASK
            y = v[p] = (v[p] - mx) & MASK
        z = v[n - 1]
        mx = ((((z >> 5) ^ (y << 2)) + ((y >> 3) ^ (z << 4))) ^
              ((total ^ y) + (k[e] ^ z))) & MASK
        y = v[0] = (v[0] - mx) & MASK
        total = (total - DELTA) & MASK
    length = v[-1]
    max_len = (n - 1) * 4
    if length < max(0, max_len - 3) or length > max_len:
        raise ValueError("invalid XXTEA include-length")
    return struct.pack("<%dI" % (n - 1), *v[:-1])[:length]


def _bounded_gzip(data: bytes, limit: int) -> bytes:
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)
    out = bytearray()
    try:
        for pos in range(0, len(data), 65536):
            if d.eof:
                raise ValueError("invalid gzip payload")
            chunk = data[pos : pos + 65536]
            out.extend(d.decompress(chunk, max(0, limit + 1 - len(out))))
            if len(out) > limit:
                raise ValueError("decoded output exceeds limit")
            if d.eof and (d.unused_data or pos + len(chunk) < len(data)):
                raise ValueError("invalid gzip payload")
        out.extend(d.flush(max(0, limit + 1 - len(out))))
    except zlib.error as exc:
        raise ValueError("invalid gzip payload") from exc
    if len(out) > limit:
        raise ValueError("decoded output exceeds limit")
    if not d.eof:
        raise ValueError("invalid gzip payload")
    if d.unused_data:
        raise ValueError("invalid gzip payload")
    return bytes(out)


def decode_payload(data: bytes, key: bytes, max_output: int = MAX_OUTPUT) -> bytes:
    if max_output < 0 or max_output > MAX_OUTPUT:
        raise ValueError("decoded output limit is invalid")
    plain = xxtea_decrypt(data, key)
    if plain[:2] == b"\x1f\x8b":
        plain = _bounded_gzip(plain, max_output)
    elif len(plain) > max_output:
        raise ValueError("decoded output exceeds limit")
    try:
        plain.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("decoded payload is not UTF-8") from exc
    return plain


def extract_vn_key(native_path: Path) -> bytes:
    path = Path(native_path).resolve()
    if path.stat().st_size != VN_NATIVE_SIZE:
        raise ValueError("native size mismatch")
    with path.open("rb") as stream:
        digest = hashlib.sha256()
        remaining = VN_NATIVE_SIZE
        while remaining:
            chunk = stream.read(min(_IO_CHUNK, remaining))
            if not chunk:
                raise ValueError("native size mismatch")
            digest.update(chunk)
            remaining -= len(chunk)
        if stream.read(1):
            raise ValueError("native size mismatch")
        if digest.hexdigest() != VN_NATIVE_SHA256:
            raise ValueError("native fingerprint mismatch")
        stream.seek(VN_KEY_OFFSET)
        key = stream.read(16)
    if len(key) != 16 or hashlib.sha256(key).hexdigest() != VN_KEY_SHA256:
        raise ValueError("native key fingerprint mismatch")
    return key


def _absolute_path(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _is_link_or_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return path.is_symlink() or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def _has_link_ancestor(path: Path) -> bool:
    absolute = _absolute_path(path)
    return any(_is_link_or_reparse(candidate) for candidate in (absolute, *absolute.parents))


def read_ciphertext(input_path: Path) -> bytes:
    path = _absolute_path(Path(input_path))
    size = path.stat().st_size
    if size > MAX_CIPHERTEXT:
        raise ValueError("ciphertext exceeds limit")
    chunks: list[bytes] = []
    remaining = size
    with path.open("rb") as stream:
        while remaining:
            chunk = stream.read(min(_IO_CHUNK, remaining))
            if not chunk:
                raise ValueError("input changed during read")
            chunks.append(chunk)
            remaining -= len(chunk)
        if stream.read(1):
            raise ValueError("ciphertext exceeds limit")
    return b"".join(chunks)


def validate_output_path(input_path: Path, output_path: Path) -> Path:
    source = _absolute_path(Path(input_path))
    target = _absolute_path(Path(output_path))
    if _has_link_ancestor(source) or _has_link_ancestor(target):
        raise ValueError("input/output must not use symlink or reparse ancestry")
    approved = [_absolute_path(ROOT / "work" / "apk-vn"), _absolute_path(ROOT / "client-recovered")]
    baseline = _absolute_path(ROOT / "work" / "apk-vn" / "20260914T180000Z")
    if target == source:
        raise ValueError("output must differ from input")
    if not any(target == base or base in target.parents for base in approved):
        raise ValueError("output must be under an approved recovery directory")
    if target == baseline or baseline in target.parents or target.suffix.lower() == ".apk":
        raise ValueError("output must not be inside the APK baseline")
    return target


def write_output(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("xb") as stream:
            stream.write(data)
    except FileExistsError as exc:
        raise ValueError("output exists; refusing to clobber") from exc


def _parse_args(argv: list[str]) -> argparse.Namespace:
    class _SanitizedArgumentParser(argparse.ArgumentParser):
        def error(self, message: str) -> None:
            raise ValueError("invalid command arguments")

    parser = _SanitizedArgumentParser(description=__doc__)
    parser.add_argument("--native", type=Path, help="verified VN lib native binary")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parse_args(argv)
        target = validate_output_path(args.input, args.output)
        if target.exists():
            raise ValueError("output exists; refusing to clobber")
        if args.native is None:
            raise ValueError("provide --native")
        key = extract_vn_key(args.native)
        decoded = decode_payload(read_ciphertext(args.input), key)
        write_output(target, decoded)
        print(json.dumps({"status": "ok", "input_bytes": args.input.stat().st_size,
                          "output_bytes": len(decoded),
                          "output_sha256": hashlib.sha256(decoded).hexdigest()}, sort_keys=True))
        return 0
    except OSError:
        print(json.dumps({"status": "error", "error": "I/O failure"}), file=sys.stderr)
        return 2
    except (TypeError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
