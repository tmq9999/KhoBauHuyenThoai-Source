"""Verify selected Apktool payloads directly against the pinned APK ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    args = parser.parse_args()
    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    try:
        with zipfile.ZipFile(args.apk) as archive:
            for name, expected in ledger["apk_payloads"].items():
                apk_data = archive.read(name)
                tree_data = (args.tree / Path(name)).read_bytes()
                apk_hash = hashlib.sha256(apk_data).hexdigest()
                tree_hash = hashlib.sha256(tree_data).hexdigest()
                if apk_hash != expected or tree_hash != apk_hash:
                    raise ValueError(f"payload mismatch: {name}")
    except (KeyError, OSError, ValueError, zipfile.BadZipFile) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print("APK_PAYLOADS_VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
