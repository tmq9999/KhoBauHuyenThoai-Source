import importlib.util
import gzip
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[2]
RUN_DIR = ROOT / "work" / "apk-vn" / "20260914T135911Z-efc5da6a"
MODULE_PATH = ROOT / "tools" / "apk-recovery" / "decode-jsc.py"
spec = importlib.util.spec_from_file_location("decode_jsc", MODULE_PATH)
decode_jsc = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(decode_jsc)


KEY = b"0123456789abcdef"
# Independent standard Cocos XXTEA reference vector for b"hello world".
VECTOR = bytes.fromhex("85412a951b720b6e74798bc055b4d6b0")
# Independent vector: gzip (wbits=31, mtime=0) of b"hello jsc", then XXTEA.
GZIP_VECTOR = bytes.fromhex(
    "dfb8b43a7cfc4f438f14478e53bea5c1c0a73338b826fadea3be5d3ceb8ad6e57c0875ec"
)
NON_UTF8_VECTOR = bytes.fromhex("4fbd534e617d27c2")  # Independent vector for b"\xff".


def test_decrypts_standard_include_length_vector():
    assert decode_jsc.decode_payload(VECTOR, KEY) == b"hello world"


def test_decrypts_and_unwraps_gzip_payload():
    assert decode_jsc.decode_payload(GZIP_VECTOR, KEY) == b"hello jsc"


@pytest.mark.parametrize("payload", [b"", b"1234567", b"not-a-multiple-of-four"])
def test_rejects_truncated_or_misaligned_ciphertext(payload):
    with pytest.raises(ValueError, match="ciphertext"):
        decode_jsc.decode_payload(payload, KEY)


def test_rejects_corrupt_include_length():
    # Decrypt to a valid block, then alter the final length word ciphertext fixture
    # by using a separately known malformed block (all zeroes cannot yield a valid
    # include-length under this key).
    with pytest.raises(ValueError, match="length|payload"):
        decode_jsc.decode_payload(bytes(16), KEY)


def test_rejects_decrypted_non_utf8_payload():
    with pytest.raises(ValueError, match="UTF-8"):
        decode_jsc.decode_payload(NON_UTF8_VECTOR, KEY)


def test_rejects_ciphertext_over_limit():
    with pytest.raises(ValueError, match="ciphertext.*limit"):
        decode_jsc.decode_payload(bytes(decode_jsc.MAX_CIPHERTEXT + 4), KEY)


def test_gzip_output_limit_is_enforced():
    with pytest.raises(ValueError, match="limit"):
        decode_jsc.decode_payload(GZIP_VECTOR, KEY, max_output=3)


def test_rejects_corrupt_gzip_stream():
    with pytest.raises(ValueError, match="gzip"):
        decode_jsc._bounded_gzip(b"\x1f\x8bbroken", 1024)


def test_gzip_rejects_trailing_data_and_concatenated_members():
    member = gzip.compress(b"first", mtime=0)
    for payload in (member + b"trailing", member + gzip.compress(b"second", mtime=0)):
        with pytest.raises(ValueError, match="gzip"):
            decode_jsc._bounded_gzip(payload, 1024)


def test_gzip_accepts_output_at_the_exact_limit():
    payload = b"x" * 64
    assert decode_jsc._bounded_gzip(gzip.compress(payload, mtime=0), len(payload)) == payload


def test_read_ciphertext_rejects_oversized_sparse_file_before_open(monkeypatch):
    ciphertext = RUN_DIR / "decoder-test-oversized.jsc"
    with ciphertext.open("wb") as stream:
        stream.truncate(decode_jsc.MAX_CIPHERTEXT + 1)

    def fail_open(self, *args, **kwargs):
        raise AssertionError("oversized input must not be opened")

    monkeypatch.setattr(Path, "open", fail_open)
    with pytest.raises(ValueError, match="ciphertext.*limit"):
        decode_jsc.read_ciphertext(ciphertext)
    ciphertext.unlink(missing_ok=True)


def test_extract_vn_key_rejects_wrong_sized_native_before_open(monkeypatch):
    native = RUN_DIR / "decoder-test-wrong-size.so"
    native.write_bytes(b"x")

    def fail_open(self, *args, **kwargs):
        raise AssertionError("wrong-sized native must not be opened")

    monkeypatch.setattr(Path, "open", fail_open)
    with pytest.raises(ValueError, match="native size"):
        decode_jsc.extract_vn_key(native)
    native.unlink(missing_ok=True)


def test_cli_argument_errors_are_sanitized_json_without_echoing_arguments(capsys):
    secret = "do-not-echo-this-key"
    assert decode_jsc.main(["--input", secret, "--output", "out.js", "--unknown", secret]) == 2
    error = capsys.readouterr().err
    assert json.loads(error) == {"status": "error", "error": "invalid command arguments"}
    assert secret not in error


def test_output_path_must_be_approved_and_not_input():
    input_path = RUN_DIR / "decoder-test-input.jsc"
    with pytest.raises(ValueError, match="output"):
        decode_jsc.validate_output_path(input_path, input_path)
    outside = ROOT / "not-approved-test-output.js"
    with pytest.raises(ValueError, match="approved"):
        decode_jsc.validate_output_path(input_path, outside)
    baseline_file = ROOT / "work" / "apk-vn" / "20260914T180000Z" / "decoded" / "out.js"
    with pytest.raises(ValueError, match="baseline"):
        decode_jsc.validate_output_path(input_path, baseline_file)


def test_output_path_rejects_symlink_ancestry_for_input_and_output(monkeypatch):
    root = RUN_DIR / "decoder-test-symlink-root"
    approved = root / "client-recovered"
    (root / "work" / "apk-vn").mkdir(parents=True, exist_ok=True)
    approved.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(decode_jsc, "ROOT", root)
    source = root / "input.jsc"
    source.write_bytes(b"ciphertext")
    input_link = root / "input-link.jsc"
    output_link = approved / "outside-link"
    outside = RUN_DIR / "decoder-test-outside"
    outside.mkdir(exist_ok=True)
    try:
        input_link.symlink_to(source)
        output_link.symlink_to(outside, target_is_directory=True)
    except OSError:
        input_link.unlink(missing_ok=True)
        output_link.unlink(missing_ok=True)
        source.unlink(missing_ok=True)
        if outside.exists():
            outside.rmdir()
        approved.rmdir()
        (root / "work" / "apk-vn").rmdir()
        (root / "work").rmdir()
        root.rmdir()
        pytest.skip("symlink creation is unavailable on this Windows test host")

    with pytest.raises(ValueError, match="symlink|reparse"):
        decode_jsc.validate_output_path(input_link, approved / "result.js")
    with pytest.raises(ValueError, match="symlink|reparse"):
        decode_jsc.validate_output_path(source, output_link / "result.js")
    output_link.unlink(missing_ok=True)
    input_link.unlink(missing_ok=True)
    source.unlink(missing_ok=True)
    outside.rmdir()
    approved.rmdir()
    (root / "work" / "apk-vn").rmdir()
    (root / "work").rmdir()
    root.rmdir()


def test_write_output_refuses_to_clobber():
    output = RUN_DIR / "decoder-test-existing.js"
    output.write_bytes(b"keep me")
    try:
        with pytest.raises(ValueError, match="clobber"):
            decode_jsc.write_output(output, b"replacement")
        assert output.read_bytes() == b"keep me"
    finally:
        output.unlink(missing_ok=True)


def test_cli_rejects_unpinned_native_with_json_error():
    encrypted = RUN_DIR / "decoder-test-input.jsc"
    output = ROOT / "client-recovered" / "test-decode-jsc-output.js"
    native = RUN_DIR / "decoder-test-native.so"
    encrypted.write_bytes(VECTOR)
    with native.open("wb") as stream:
        stream.truncate(decode_jsc.VN_NATIVE_SIZE)
    output.unlink(missing_ok=True)
    try:
        proc = subprocess.run(
            [
                sys.executable,
                str(MODULE_PATH),
                "--native",
                str(native),
                "--input",
                str(encrypted),
                "--output",
                str(output),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        assert proc.returncode == 2
        info = json.loads(proc.stderr)
        assert info == {"status": "error", "error": "native fingerprint mismatch"}
        assert not output.exists()
    finally:
        encrypted.unlink(missing_ok=True)
        native.unlink(missing_ok=True)
        output.unlink(missing_ok=True)
