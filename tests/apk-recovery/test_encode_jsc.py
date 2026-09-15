import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[2]
RUN_DIR = ROOT / "work" / "apk-vn" / "20260914T135911Z-efc5da6a"
ENCODER_PATH = ROOT / "tools" / "apk-recovery" / "encode-jsc.py"
DECODER_PATH = ROOT / "tools" / "apk-recovery" / "decode-jsc.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


encode_jsc = load_module("encode_jsc", ENCODER_PATH)
decode_jsc = load_module("decode_jsc", DECODER_PATH)

KEY = b"0123456789abcdef"
VECTOR = bytes.fromhex("85412a951b720b6e74798bc055b4d6b0")


def test_encrypts_standard_include_length_known_answer_without_compression():
    assert encode_jsc.encode_payload(b"hello world", KEY, compress=False) == VECTOR


def test_deterministic_gzip_encoder_round_trips_through_decoder():
    source = b"const greeting = 'hello jsc';\n"
    encoded = encode_jsc.encode_payload(source, KEY)
    assert encoded == encode_jsc.encode_payload(source, KEY)
    assert decode_jsc.decode_payload(encoded, KEY) == source


def test_rejects_non_utf8_and_oversized_source():
    with pytest.raises(ValueError, match="UTF-8"):
        encode_jsc.encode_payload(b"\xff", KEY)
    with pytest.raises(ValueError, match="limit"):
        encode_jsc.encode_payload(b"x" * (encode_jsc.MAX_INPUT + 1), KEY)


def test_rejects_encoded_output_over_limit(monkeypatch):
    monkeypatch.setattr(encode_jsc, "MAX_ENCODED", len(VECTOR) - 1)
    with pytest.raises(ValueError, match="encoded.*limit"):
        encode_jsc.encode_payload(b"hello world", KEY, compress=False)


def test_read_source_rejects_oversized_file_before_open(monkeypatch):
    source = RUN_DIR / "encoder-test-oversized.js"
    with source.open("wb") as stream:
        stream.truncate(encode_jsc.MAX_INPUT + 1)

    def fail_open(self, *args, **kwargs):
        raise AssertionError("oversized input must not be opened")

    monkeypatch.setattr(Path, "open", fail_open)
    try:
        with pytest.raises(ValueError, match="input.*limit"):
            encode_jsc.read_source(source)
    finally:
        monkeypatch.undo()
        source.unlink(missing_ok=True)


def test_cli_argument_errors_are_sanitized_json_without_echoing_arguments(capsys):
    secret = "do-not-echo-this-key"
    assert encode_jsc.main(["--input", secret, "--output", "out.jsc", "--unknown", secret]) == 2
    error = capsys.readouterr().err
    assert json.loads(error) == {"status": "error", "error": "invalid command arguments"}
    assert secret not in error


def test_cli_rejects_output_outside_decoder_approved_roots(capsys):
    source = RUN_DIR / "encoder-test-source.js"
    source.write_text("let x = 1;", encoding="utf-8")
    try:
        assert encode_jsc.main([
            "--native", str(RUN_DIR / "unused-native.so"),
            "--input", str(source), "--output", str(ROOT / "outside.jsc"),
        ]) == 2
        assert json.loads(capsys.readouterr().err) == {
            "status": "error", "error": "output must be under an approved recovery directory"
        }
    finally:
        source.unlink(missing_ok=True)
