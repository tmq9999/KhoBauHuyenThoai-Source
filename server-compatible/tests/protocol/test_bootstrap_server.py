import http.client
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import io

import pytest


ROOT = Path(__file__).parents[3]
SERVER_PATH = ROOT / "server-compatible" / "src" / "bootstrap_server.py"


def _server_module():
    spec = importlib.util.spec_from_file_location("bootstrap_server", SERVER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _manifest() -> dict:
    return {
        "version": "1.0.0.02",
        "host": "127.0.0.1:20001",
        "remoteVersionUrl": "http://127.0.0.1:20001/update/version.manifest",
        "remoteManifestUrl": "http://127.0.0.1:20001/update/project.manifest",
        "packageUrl": "http://127.0.0.1:20001/update/1.0.0.02",
        "assets": {
            "src/project.jsc": {"md5": "0d7b1c2f0fc9766311451cc6d6a76877"},
            "src/settings.jsc": {"md5": "b3d27c4232eca4cde2c4617a7fd7da7b"},
            "src/jsb_polyfill.jsc": {"md5": "18b0c7fba10e6a8ca524f25678764c3a"},
        },
    }


def _get(server, path: str):
    connection = http.client.HTTPConnection(server.host, server.port, timeout=2)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


def _head(server, path: str):
    connection = http.client.HTTPConnection(server.host, server.port, timeout=2)
    try:
        connection.request("HEAD", path)
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


def _post(server, path: str, body: str, content_type: str = "application/x-www-form-urlencoded"):
    connection = http.client.HTTPConnection(server.host, server.port, timeout=2)
    try:
        connection.request("POST", path, body=body, headers={"Content-Type": content_type})
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


def test_local_account_login_is_stable_and_wrong_password_is_sanitized(tmp_path, capsys):
    module = _server_module()
    manifest_path = tmp_path / "project.manifest"
    manifest_path.write_text(json.dumps(_manifest()), encoding="utf-8")
    server = module.BootstrapHTTPServer.start_in_thread(manifest_path, port=0)
    try:
        status, body = _post(server, "/user/login", "name=alice&password=secret")
        first = json.loads(body)
        assert status == 200 and set(first) == {"uid", "token"}
        status, body = _post(server, "/user/login", "name=alice&password=secret")
        assert json.loads(body) == first
        status, body = _post(server, "/user/login", "name=alice&password=wrong")
        assert status == 200 and json.loads(body)["code"] == 500
        status, body = _post(server, "/user/register", "name=bob&password=pw")
        assert json.loads(body) == {"code": 0, "msg": "ok"}
        status, body = _post(server, "/user/register", "name=bob&password=other")
        assert status == 200 and json.loads(body)["code"] == 500
        status, body = _post(server, "/user/login", "name=bob&password=pw")
        assert set(json.loads(body)) == {"uid", "token"}
        status, body = _post(server, "/user/login", "name=%20alice%20&password=%20secret%20")
        spaced = json.loads(body)
        assert set(spaced) == {"uid", "token"} and spaced != first
        assert b"secret" not in repr(server._httpd.accounts).encode("utf-8")
        status, body = _post(server, "/user/serverInfo", "userName=alice")
        info = json.loads(body)
        assert info == {"serverList": [{"serverId": 1, "oldServerId": 1, "name": "1区"}], "players": []}
        status, body = _post(server, "/user/login", "name=alice&password=secret", "text/plain")
        assert status == 400 and json.loads(body)["error"] == "bad request"
        status, body = _get(server, "/user/login")
        assert status == 404 and json.loads(body)["error"] == "not found"
        logs = capsys.readouterr().err
        for value in ("alice", "secret", "wrong", "bob", "pw"):
            assert value not in logs
    finally:
        server.close()


@pytest.mark.parametrize("body", ["name=a%", "name=a%0", "name=a%ZZ", "name=%FF", "name=%E2%82"])
def test_account_routes_reject_malformed_percent_or_utf8_without_account_mutation(tmp_path, body):
    module = _server_module()
    manifest_path = tmp_path / "project.manifest"
    manifest_path.write_text(json.dumps(_manifest()), encoding="utf-8")
    server = module.BootstrapHTTPServer.start_in_thread(manifest_path, port=0)
    try:
        status, payload = _post(server, "/user/register", body + "&password=pw")
        assert status == 400 and json.loads(payload) == {"error": "bad request"}
        assert not server._httpd.accounts
    finally:
        server.close()


def test_account_form_preserves_spaces_plus_and_percent_encoding(tmp_path):
    module = _server_module()
    manifest_path = tmp_path / "project.manifest"
    manifest_path.write_text(json.dumps(_manifest()), encoding="utf-8")
    server = module.BootstrapHTTPServer.start_in_thread(manifest_path, port=0)
    try:
        status, payload = _post(server, "/user/register", "name=a+b%20c&password=p%25%20w")
        assert status == 200 and json.loads(payload)["code"] == 0
        status, payload = _post(server, "/user/login", "name=a+b%20c&password=p%25%20w")
        assert set(json.loads(payload)) == {"uid", "token"}
    finally:
        server.close()


def test_loopback_bootstrap_serves_source_derived_handshake_and_exact_manifest(tmp_path, capsys):
    module = _server_module()
    manifest_path = tmp_path / "project.manifest"
    manifest_path.write_text(json.dumps(_manifest(), separators=(",", ":")), encoding="utf-8")
    server = module.BootstrapHTTPServer.start_in_thread(manifest_path, port=0)
    try:
        status, body = _get(server, "/client_config.json")
        assert status == 200
        assert json.loads(body) == {"runScriptInfo": {"script": ""}, "inReviewPackageInfos": []}
        assert "aliasUrl" not in json.loads(body)

        status, body = _get(server, "/update/version.manifest")
        assert (status, json.loads(body)) == (200, {"version": "1.0.0.02"})

        status, body = _get(server, "/update/project.manifest")
        assert status == 200
        assert body == manifest_path.read_bytes()

        status, body = _get(server, "/notice.json")
        assert (status, json.loads(body)) == (200, [])

        status, body = _get(server, "/assets/src/project.jsc?key=must-not-log")
        assert status == 404
        assert json.loads(body) == {"error": "not found"}
        logs = capsys.readouterr().err
        assert "must-not-log" not in logs
        assert "GET unknown 404" in logs
        assert "/assets/src/project.jsc" not in logs
    finally:
        server.close()


@pytest.mark.parametrize(
    "path",
    [
        "/client_config.json",
        "/update/version.manifest",
        "/update/project.manifest",
        "/notice.json",
    ],
)
def test_head_known_metadata_route_matches_get_status_and_headers_without_a_body(tmp_path, path):
    module = _server_module()
    manifest_path = tmp_path / "project.manifest"
    manifest_path.write_text(json.dumps(_manifest(), separators=(",", ":")), encoding="utf-8")
    server = module.BootstrapHTTPServer.start_in_thread(manifest_path, port=0)
    try:
        get_status, get_body = _get(server, path)
        head_status, head_headers, head_body = _head(server, path)

        assert (head_status, head_body) == (get_status, b"")
        assert head_headers["Content-Type"] == "application/json"
        assert head_headers["Content-Length"] == str(len(get_body))
        assert "Accept-Ranges" not in head_headers
    finally:
        server.close()


@pytest.mark.parametrize(
    "change",
    [
        {"remoteVersionUrl": "http://example.invalid/update/version.manifest"},
        {"remoteManifestUrl": "http://127.0.0.1:20001/elsewhere/project.manifest"},
        {"packageUrl": "http://127.0.0.1:20001/update/other"},
        {"host": "example.invalid"},
    ],
)
def test_manifest_loader_rejects_non_local_or_wrong_update_paths(tmp_path, change):
    module = _server_module()
    manifest = _manifest()
    manifest.update(change)
    path = tmp_path / "invalid.manifest"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError):
        module.load_lab_manifest(path)


def test_manifest_loader_refuses_symlink_and_oversized_manifest(tmp_path):
    module = _server_module()
    target = tmp_path / "target.manifest"
    target.write_text(json.dumps(_manifest()), encoding="utf-8")
    link = tmp_path / "linked.manifest"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("Windows symlink privilege unavailable")
    with pytest.raises(ValueError, match="symlink"):
        module.load_lab_manifest(link)

    oversized = tmp_path / "oversized.manifest"
    oversized.write_bytes(b" " * (2 * 1024 * 1024))
    with pytest.raises(ValueError, match="2 MiB"):
        module.load_lab_manifest(oversized)


def test_manifest_loader_bounds_bytes_actually_read_not_only_stat_size():
    module = _server_module()
    manifest = _manifest()
    manifest["padding"] = "x" * (2 * 1024 * 1024)
    raw = json.dumps(manifest).encode("utf-8")

    class LyingManifest:
        def is_symlink(self):
            return False

        def is_file(self):
            return True

        def stat(self):
            return SimpleNamespace(st_size=1)

        def open(self, mode):
            assert mode == "rb"
            return io.BytesIO(raw)

    with pytest.raises(ValueError, match="2 MiB"):
        module.load_lab_manifest(LyingManifest())


def test_bootstrap_server_returns_sanitized_json_404_for_all_unsupported_verbs(tmp_path, capsys):
    module = _server_module()
    manifest_path = tmp_path / "project.manifest"
    manifest_path.write_text(json.dumps(_manifest()), encoding="utf-8")
    server = module.BootstrapHTTPServer.start_in_thread(manifest_path, port=0)
    secret_path = "/not-supported?key=must-not-log"
    try:
        connection = http.client.HTTPConnection(server.host, server.port, timeout=2)
        connection.request("BREW", secret_path, "password=must-not-log")
        response = connection.getresponse()
        assert response.status == 404
        assert json.loads(response.read()) == {"error": "not found"}
        connection.close()

        connection = http.client.HTTPConnection(server.host, server.port, timeout=2)
        connection.request("HEAD", secret_path)
        response = connection.getresponse()
        assert response.status == 404
        assert response.read() == b""
        connection.close()

        logs = capsys.readouterr().err
        assert "BREW" not in logs
        assert "must-not-log" not in logs
        assert "unsupported unknown 404" in logs
        assert "HEAD unknown 404" in logs
    finally:
        server.close()
