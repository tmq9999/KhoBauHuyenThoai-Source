import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
ENTRY = ROOT / "tools/protocol/route_inventory.py"
SOURCE = ROOT / "client-recovered/src/project.js"
PINNED_SHA = "9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818"


@pytest.fixture(scope="module")
def extractor():
    assert ENTRY.is_file(), "M0.1 route inventory implementation is missing"
    spec = importlib.util.spec_from_file_location("route_inventory", ENTRY)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_request_inventory_keeps_source_line_and_route(extractor):
    source = 'x = 1;\na.request("logic.playerHandler.buyCoin", {}, cb);\n'
    assert extractor.inventory(source) == [{
        "route": "logic.playerHandler.buyCoin", "sourceLine": 2, "status": "STATIC_OBSERVED",
    }]


@pytest.mark.parametrize("source", [
    'var text = \'a.request("logic.playerHandler.buyCoin", {}, cb)\';',
    '// a.request("logic.playerHandler.buyCoin", {}, cb);',
    '/*\na.request("logic.playerHandler.buyCoin", {}, cb);\n*/',
    'var text = `a.request("logic.playerHandler.buyCoin", {}, cb);`;',
    r'var rx = /a.request("logic.playerHandler.buyCoin", {}, cb)/;',
    r'if (ok) /a.request("logic.playerHandler.buyCoin", {}, cb)/.test(text);',
    'var text = "logic.playerHandler.buyCoin";',
    'a.request("https://provider.invalid/login", {}, cb);',
    'a.request("logic.playerHandler.buy" + suffix, {}, cb);',
])
def test_nonliteral_or_inert_text_is_not_a_route(extractor, source):
    assert extractor.inventory(source) == []


def test_preserves_duplicate_sites_and_crlf_line_numbers(extractor):
    source = 'socket.request(\r\n "logic.playerHandler.buyCoin", {}, cb);\r\n' \
             'other.request(\'logic.playerHandler.buyCoin\', {}, cb);\r\n'
    assert extractor.inventory(source) == [
        {"route": "logic.playerHandler.buyCoin", "sourceLine": 1, "status": "STATIC_OBSERVED"},
        {"route": "logic.playerHandler.buyCoin", "sourceLine": 3, "status": "STATIC_OBSERVED"},
    ]


def test_request_keys_only_include_top_level_object_keys(extractor):
    source = 'a.request("logic.teamHandler.test", {teamIndex: x, nested: {key: 1}, list: [1, 2], "quoted": true}, cb);'
    record = extractor.analyze(source)["calls"][0]
    assert record["requestKeys"] == ["teamIndex", "nested", "list", "quoted"]
    assert record["requestShape"] == "OBJECT_KEYS_ONLY"
    assert record["sourceLine"] == 1


def test_dynamic_payload_is_explicitly_unknown(extractor):
    record = extractor.analyze('a.request("logic.teamHandler.test", opts, cb);')["calls"][0]
    assert record["requestKeys"] is None
    assert record["requestShape"] == "DYNAMIC"


def test_direct_adjacent_variable_route_is_resolved_and_wrapper_is_not(extractor):
    source = 'function init() {\nvar route = "gate.gateHandler.queryEntry";\na.request(route, {uid: user}, cb);\n}\n' \
             'function wrapper(route, body, cb) { a.request(route, body, cb); }'
    analysis = extractor.analyze(source)
    assert len(analysis["calls"]) == 1
    call = analysis["calls"][0]
    assert (call["route"], call["sourceLine"], call["declarationLine"], call["requestKeys"]) == (
        "gate.gateHandler.queryEntry", 3, 2, ["uid"],
    )
    assert call["routeBinding"] == "ADJACENT_LITERAL"
    assert analysis["dynamicRequests"] == [{"sourceLine": 5, "reason": "NON_LITERAL_ROUTE"}]


def test_reassigned_or_conditional_route_is_not_guessed(extractor):
    sources = [
        'var route = "logic.a.b"; route = other; a.request(route, {}, cb);',
        'if (flag) var route = "logic.a.b"; a.request(route, {}, cb);',
        'function outer(){ var route = "logic.a.b"; } a.request(route, {}, cb);',
    ]
    for source in sources:
        analysis = extractor.analyze(source)
        assert analysis["calls"] == []
        assert len(analysis["dynamicRequests"]) == 1


def test_division_does_not_hide_a_later_real_request(extractor):
    source = 'var n = total / count; a.request("logic.playerHandler.buyCoin", {}, cb);'
    assert len(extractor.inventory(source)) == 1


def test_unknown_handler_is_not_silently_marked_core(extractor):
    assert extractor.classify("logic.mysteryHandler.addCoins") == "BLOCKED_EVIDENCE"


def test_unterminated_request_returns_sanitized_failure(extractor):
    with pytest.raises(ValueError, match="MALFORMED_REQUEST_CALL"):
        extractor.analyze('a.request("logic.playerHandler.buyCoin", {')


def test_regex_comment_or_string_key_is_not_a_nested_request(extractor):
    source = '/* ignore */ a.request("logic.playerHandler.useItem", {x: /[{}]/, y: "}", nested: {k: [1,2]}}, cb);'
    assert extractor.analyze(source)["calls"][0]["requestKeys"] == ["x", "y", "nested"]


def _cli(*args):
    return subprocess.run([sys.executable, str(ENTRY), *map(str, args)], cwd=ROOT,
                          capture_output=True, text=True, timeout=30)


def test_cli_generates_pinned_manifest_and_check_does_not_write(tmp_path):
    output = tmp_path / "inventory.json"
    assert ENTRY.is_file(), "M0.1 route inventory CLI is missing"
    run = _cli("--source", SOURCE, "--output", output)
    assert run.returncode == 0, run.stderr
    raw = output.read_bytes()
    manifest = json.loads(raw)
    assert manifest["source"]["sha256"] == PINNED_SHA
    assert manifest["formatVersion"] == 1
    assert manifest["status"] == "STATIC_OBSERVED"
    routes = {route["route"]: route for route in manifest["routes"]}
    assert routes["logic.playerHandler.buyCoin"]["tier"] == "CORE"
    assert routes["logic.gmHandler.addItem"]["tier"] == "DENIED_ADMIN_ONLY"
    assert routes["logic.arenaHandler.challenge"]["tier"] == "EXPANSION"
    assert routes["gate.gateHandler.queryEntry"]["sites"][0]["requestKeys"] == ["uid"]
    assert routes["connector.entryHandler.entry"]["sites"][0]["requestKeys"] == ["token", "serverId", "oldServerId"]
    timestamp = output.stat().st_mtime_ns
    assert _cli("--source", SOURCE, "--output", output, "--check").returncode == 0
    assert _cli("--source", SOURCE, "--output", output).returncode == 0
    assert output.read_bytes() == raw
    assert output.stat().st_mtime_ns == timestamp


def test_cli_rejects_wrong_source_without_writing_or_echoing_source(tmp_path):
    assert ENTRY.is_file(), "M0.1 route inventory CLI is missing"
    source = tmp_path / "project.js"
    source.write_text('secret-sentinel; a.request("logic.playerHandler.buyCoin", {}, cb);', encoding="utf-8")
    output = tmp_path / "inventory.json"
    run = _cli("--source", source, "--output", output)
    assert run.returncode != 0
    assert "SOURCE_HASH_MISMATCH" in run.stderr
    assert "secret-sentinel" not in run.stdout + run.stderr
    assert not output.exists()


def test_cli_refuses_clobber_and_check_missing_is_read_only(tmp_path):
    assert ENTRY.is_file(), "M0.1 route inventory CLI is missing"
    output = tmp_path / "new-parent/inventory.json"
    assert _cli("--source", SOURCE, "--output", output, "--check").returncode != 0
    assert not output.parent.exists()
    output.parent.mkdir()
    output.write_bytes(b"important existing report")
    for mode in ([], ["--check"], ["--update"]):
        run = _cli("--source", SOURCE, "--output", output, *mode)
        assert run.returncode != 0
        assert output.read_bytes() == b"important existing report"


def test_cli_only_updates_a_manifest_owned_by_this_generator(tmp_path):
    assert ENTRY.is_file(), "M0.1 route inventory CLI is missing"
    output = tmp_path / "inventory.json"
    assert _cli("--source", SOURCE, "--output", output).returncode == 0
    original = output.read_bytes()
    changed = json.loads(original)
    changed["routes"] = []
    output.write_text(json.dumps(changed), encoding="utf-8")
    stale = output.read_bytes()
    assert _cli("--source", SOURCE, "--output", output, "--check").returncode != 0
    assert output.read_bytes() == stale
    assert _cli("--source", SOURCE, "--output", output, "--update").returncode == 0
    assert output.read_bytes() == original


def test_update_rejects_malformed_manifest_identity_without_traceback(tmp_path):
    assert ENTRY.is_file()
    output = tmp_path / "bad.json"
    output.write_text(json.dumps({"generator": "kbht-vn-route-inventory", "formatVersion": 1, "source": []}))
    before = output.read_bytes()
    run = _cli("--source", SOURCE, "--output", output, "--update")
    assert run.returncode == 1
    assert run.stderr.strip() == "OUTPUT_NOT_OWNED"
    assert output.read_bytes() == before


def test_symlink_output_cannot_overwrite_target(tmp_path):
    assert ENTRY.is_file()
    target = tmp_path / "important.txt"
    target.write_text("kept", encoding="utf-8")
    link = tmp_path / "inventory.json"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink privilege unavailable")
    run = _cli("--source", SOURCE, "--output", link, "--update")
    assert run.returncode == 1
    assert run.stderr.strip() == "OUTPUT_SYMLINK"
    assert target.read_text(encoding="utf-8") == "kept"


def test_cli_never_overwrites_input_source(tmp_path):
    assert ENTRY.is_file(), "M0.1 route inventory CLI is missing"
    before = SOURCE.read_bytes()
    run = _cli("--source", SOURCE, "--output", SOURCE, "--update")
    assert run.returncode != 0
    assert SOURCE.read_bytes() == before


def test_consumer_map_must_cover_core_routes_and_match_source(extractor):
    manifest = {"source": {"sha256": PINNED_SHA}, "routes": [
        {"route": "logic.playerHandler.buyCoin", "tier": "CORE"},
    ]}
    consumers = {"sourceSha256": PINNED_SHA, "profiles": {"beli": {
        "lines": [16118], "directReads": ["_temp.costGem"], "stateReads": ["coin"],
    }}, "routes": {"logic.playerHandler.buyCoin": "beli"}}
    assert extractor.validate_consumers(consumers, manifest) is None
    for bad in ({**consumers, "sourceSha256": "0" * 64},
                {**consumers, "routes": {}},
                {**consumers, "profiles": {}},
                {**consumers, "routes": {"logic.playerHandler.buyCoin": "missing"}}):
        with pytest.raises(ValueError, match="CONSUMER"):
            extractor.validate_consumers(bad, manifest)


def test_cli_checks_reviewed_consumer_artifact_without_writes(tmp_path):
    assert ENTRY.is_file()
    manifest = tmp_path / "inventory.json"
    consumers = ROOT / "docs/protocol/vn-core-consumers.json"
    assert _cli("--source", SOURCE, "--output", manifest).returncode == 0
    result = _cli("--source", SOURCE, "--output", manifest, "--check", "--consumers", consumers)
    assert result.returncode == 0, result.stderr
