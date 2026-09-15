"""Narrow, bounded Cocos XXTEA encoder for verified JSC recovery artifacts."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys


_DECODER_PATH = Path(__file__).with_name("decode-jsc.py")
_SPEC = importlib.util.spec_from_file_location("_decode_jsc", _DECODER_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError("decoder support unavailable")
decoder = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(decoder)

DELTA = 0x9E3779B9
MASK = 0xFFFFFFFF
MAX_INPUT = decoder.MAX_OUTPUT
MAX_ENCODED = decoder.MAX_CIPHERTEXT
_IO_CHUNK = 1024 * 1024


def _words(data: bytes) -> list[int]:
    return list(struct.unpack("<%dI" % (len(data) // 4), data))


def _normalize_key(key: bytes) -> list[int]:
    if not isinstance(key, (bytes, bytearray)):
        raise TypeError("key must be bytes")
    return _words(bytes(key)[:16].ljust(16, b"\0"))


def xxtea_encrypt(data: bytes, key: bytes) -> bytes:
    """Encrypt Cocos' little-endian, include-length XXTEA representation."""
    if not data:
        raise ValueError("source must not be empty")
    padded = data + (b"\0" * (-len(data) % 4))
    v = _words(padded) + [len(data)]
    n = len(v)
    k = _normalize_key(key)
    rounds = 6 + 52 // n
    total = 0
    z = v[-1]
    for _ in range(rounds):
        total = (total + DELTA) & MASK
        e = (total >> 2) & 3
        for p in range(n - 1):
            y = v[p + 1]
            mx = ((((z >> 5) ^ (y << 2)) + ((y >> 3) ^ (z << 4))) ^
                  ((total ^ y) + (k[(p & 3) ^ e] ^ z))) & MASK
            z = v[p] = (v[p] + mx) & MASK
        y = v[0]
        mx = ((((z >> 5) ^ (y << 2)) + ((y >> 3) ^ (z << 4))) ^
              ((total ^ y) + (k[((n - 1) & 3) ^ e] ^ z))) & MASK
        z = v[-1] = (v[-1] + mx) & MASK
    return struct.pack("<%dI" % n, *v)


def encode_payload(data: bytes, key: bytes, compress: bool = True) -> bytes:
    if not isinstance(data, bytes):
        raise TypeError("source must be bytes")
    if len(data) > MAX_INPUT:
        raise ValueError("input exceeds limit")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("source is not UTF-8") from exc
    if compress:
        data = gzip.compress(data, mtime=0)
    encoded = xxtea_encrypt(data, key)
    if len(encoded) > MAX_ENCODED:
        raise ValueError("encoded output exceeds limit")
    return encoded


def read_source(input_path: Path) -> bytes:
    path = Path(input_path)
    size = path.stat().st_size
    if size > MAX_INPUT:
        raise ValueError("input exceeds limit")
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
            raise ValueError("input exceeds limit")
    return b"".join(chunks)


class _SanitizedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError("invalid command arguments")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = _SanitizedArgumentParser(description=__doc__)
    parser.add_argument("--native", type=Path, required=True, help="verified VN native binary")
    parser.add_argument("--input", type=Path, required=True, help="UTF-8 JavaScript source")
    parser.add_argument("--output", type=Path, required=True, help="new encrypted JSC path")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parse_args(argv)
        target = decoder.validate_output_path(args.input, args.output)
        if target.exists():
            raise ValueError("output exists; refusing to clobber")
        source = read_source(args.input)
        key = decoder.extract_vn_key(args.native)
        encoded = encode_payload(source, key)
        decoder.write_output(target, encoded)
        print(json.dumps({"status": "ok", "input_bytes": len(source),
                          "output_bytes": len(encoded),
                          "output_sha256": hashlib.sha256(encoded).hexdigest()}, sort_keys=True))
        return 0
    except OSError:
        print(json.dumps({"status": "error", "error": "I/O failure"}), file=sys.stderr)
        return 2
    except (TypeError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
