"""Loopback-only HTTP bootstrap service for the recovered native client.

This serves metadata required to reach the original login scene.  It is not a
general file server and deliberately has no authentication or game routes.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.parse import parse_qs, urlsplit
from typing import Any


MAX_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_FORM_BYTES = 64 * 1024
LOOPBACK_HOST = "127.0.0.1"
LOCAL_ORIGIN = "http://127.0.0.1:20001"
ROUTES = {
    "/client_config.json",
    "/update/version.manifest",
    "/update/project.manifest",
    "/notice.json",
}


class _Account:
    __slots__ = ("salt", "digest", "uid", "token")

    def __init__(self, salt: bytes, digest: bytes, uid: str, token: str):
        self.salt, self.digest, self.uid, self.token = salt, digest, uid, token


def _load_lab_manifest_bytes(path: Path) -> tuple[dict[str, Any], bytes]:
    if path.is_symlink():
        raise ValueError("manifest must not be a symlink")
    if not path.is_file():
        raise ValueError(f"manifest is missing: {path}")
    try:
        with path.open("rb") as manifest_file:
            raw = manifest_file.read(MAX_MANIFEST_BYTES + 1)
        if len(raw) >= MAX_MANIFEST_BYTES:
            raise ValueError("manifest exceeds 2 MiB")
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("manifest is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("manifest must be a JSON object")
    version = value.get("version")
    if not isinstance(version, str) or not version or "/" in version or "\\" in version:
        raise ValueError("manifest version is invalid")
    if value.get("host") != "127.0.0.1:20001":
        raise ValueError("manifest host must be loopback")
    expected_urls = {
        "remoteVersionUrl": f"{LOCAL_ORIGIN}/update/version.manifest",
        "remoteManifestUrl": f"{LOCAL_ORIGIN}/update/project.manifest",
        "packageUrl": f"{LOCAL_ORIGIN}/update/{version}",
    }
    for key, expected in expected_urls.items():
        if value.get(key) != expected:
            raise ValueError(f"manifest {key} must use the loopback update path")
        parsed = urlsplit(value[key])
        if parsed.scheme != "http" or parsed.hostname != LOOPBACK_HOST or parsed.port != 20001 or parsed.query or parsed.fragment:
            raise ValueError(f"manifest {key} must use the loopback origin")
    assets = value.get("assets")
    if not isinstance(assets, dict):
        raise ValueError("manifest assets must be an object")
    for asset_path, entry in assets.items():
        if not isinstance(asset_path, str) or asset_path.startswith(("/", "\\")) or ".." in Path(asset_path).parts:
            raise ValueError("manifest asset paths must be relative")
        if not isinstance(entry, dict) or not isinstance(entry.get("md5"), str):
            raise ValueError("manifest asset entries must contain md5")
    return value, raw


def load_lab_manifest(path: Path) -> dict[str, Any]:
    """Validate a manifest without serving it (used by focused checks/tests)."""
    return _load_lab_manifest_bytes(path)[0]


class _BootstrapHandler(BaseHTTPRequestHandler):
    server_version = "RecoveredBootstrap/1.0"

    def _reply(self, status: int, body: bytes) -> None:
        route_label = urlsplit(self.path).path if status == 200 else "unknown"
        method_label = self.command if self.command in {"GET", "HEAD", "POST"} else "unsupported"
        self.server.record(method_label, route_label, status)  # type: ignore[attr-defined]
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _fixed_route_response(self) -> tuple[int, bytes]:
        path = urlsplit(self.path)
        if path.query or path.fragment or path.path not in ROUTES:
            return 404, b'{"error":"not found"}'
        if path.path == "/client_config.json":
            return 200, b'{"runScriptInfo":{"script":""},"inReviewPackageInfos":[]}'
        if path.path == "/notice.json":
            return 200, b"[]"
        if path.path == "/update/version.manifest":
            body = json.dumps({"version": self.server.manifest["version"]}, separators=(",", ":")).encode()  # type: ignore[attr-defined]
            return 200, body
        return 200, self.server.manifest_bytes  # type: ignore[attr-defined]

    def _serve_fixed_route(self) -> None:
        status, body = self._fixed_route_response()
        self._reply(status, body)

    def do_GET(self) -> None:  # noqa: N802
        self._serve_fixed_route()

    def do_POST(self) -> None:  # noqa: N802
        path = urlsplit(self.path)
        if path.query or path.fragment:
            self._reply(404, b'{"error":"not found"}')
            return
        if path.path not in {"/user/login", "/user/register", "/user/serverInfo"}:
            self._reply(404, b'{"error":"not found"}')
            return
        form = self._read_form()
        if form is None:
            self._reply(400, b'{"error":"bad request"}')
            return
        if path.path == "/user/login":
            name, password = self._required(form, "name", "password")
            if name is None or password is None:
                self._reply(400, b'{"error":"bad request"}')
                return
            account = self.server.login_account(name, password)  # type: ignore[attr-defined]
            if account is None:
                self._reply(200, json.dumps({"code": 500, "msg": "Tài khoản hoặc mật khẩu không đúng"}, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
                return
            self._reply(200, json.dumps({"uid": account[0], "token": account[1]}, separators=(",", ":")).encode())
            return
        if path.path == "/user/register":
            name, password = self._required(form, "name", "password")
            if name is None or password is None:
                self._reply(400, b'{"error":"bad request"}')
                return
            if not self.server.register_account(name, password):  # type: ignore[attr-defined]
                self._reply(200, b'{"code":500,"msg":"account exists"}')
                return
            self._reply(200, b'{"code":0,"msg":"ok"}')
            return
        (name,) = self._required(form, "userName")
        if name is None:
            self._reply(400, b'{"error":"bad request"}')
            return
        self._reply(200, json.dumps({"serverList": [{"serverId": 1, "oldServerId": 1, "name": "1区"}], "players": []}, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    def _required(self, form: dict[str, list[str]], *keys: str) -> tuple[str | None, ...]:
        values: list[str | None] = []
        for key in keys:
            candidates = form.get(key)
            value = candidates[0] if candidates and len(candidates) == 1 else None
            values.append(value if value is not None and value != "" else None)
        return tuple(values)

    def _read_form(self) -> dict[str, list[str]] | None:
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/x-www-form-urlencoded":
            return None
        try:
            length = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            return None
        if length < 0 or length > MAX_FORM_BYTES:
            return None
        raw = self.rfile.read(length)
        if len(raw) != length:
            return None
        try:
            for index, byte in enumerate(raw):
                if byte == 0x25 and (index + 2 >= len(raw) or any(c not in b"0123456789abcdefABCDEF" for c in raw[index + 1:index + 3])):
                    return None
            encoded = raw.decode("utf-8")
            return parse_qs(encoded, keep_blank_values=True, strict_parsing=True, encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, ValueError):
            return None

    def do_HEAD(self) -> None:  # noqa: N802
        self._serve_fixed_route()

    def send_error(self, code: int, message: str | None = None, explain: str | None = None) -> None:
        # BaseHTTPRequestHandler sends 501 HTML for unknown do_<VERB>.  The
        # bootstrap surface has one uniform, JSON-only unknown-route response.
        self._reply(404, b'{"error":"not found"}')

    def log_message(self, fmt: str, *args: object) -> None:
        # Request details (query, headers, and body) are intentionally omitted.
        return


class _Server(ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(self, manifest_path: Path, port: int, account_service: Any | None = None):
        self.manifest, self.manifest_bytes = _load_lab_manifest_bytes(manifest_path)
        self.accounts: dict[str, _Account] = {}
        self.account_lock = threading.RLock()
        self.account_service = account_service
        self.counts: dict[tuple[str, str, int], int] = {}
        super().__init__((LOOPBACK_HOST, port), _BootstrapHandler)

    def _new_account(self, name: str, password: str) -> "_Account":
        salt = secrets.token_bytes(16)
        digest = hashlib.sha256(salt + password.encode("utf-8")).digest()
        stable = hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]
        return _Account(salt, digest, f"lab-{stable}", f"lab-{secrets.token_urlsafe(32)}")

    def ensure_account(self, name: str, password: str) -> tuple[str, str]:
        with self.account_lock:
            account = self.accounts.get(name)
            if account is None:
                account = self._new_account(name, password)
                self.accounts[name] = account
            return account.uid, account.token

    def register_account(self, name: str, password: str) -> bool:
        if self.account_service is not None:
            return self.account_service.register_account(name, password)
        with self.account_lock:
            account = self.accounts.get(name)
            if account is not None:
                return hmac.compare_digest(account.digest, hashlib.sha256(account.salt + password.encode("utf-8")).digest())
            self.accounts[name] = self._new_account(name, password)
            return True

    def login_account(self, name: str, password: str) -> tuple[str, str] | None:
        if self.account_service is not None:
            return self.account_service.login_account(name, password)
        with self.account_lock:
            account = self.accounts.get(name)
            if account is None:
                account = self._new_account(name, password)
                self.accounts[name] = account
            digest = hashlib.sha256(account.salt + password.encode("utf-8")).digest()
            if not hmac.compare_digest(account.digest, digest):
                return None
            return account.uid, account.token

    def authenticate_token(self, token: str) -> dict[str, str] | None:
        if self.account_service is not None:
            return self.account_service.authenticate_token(token)
        with self.account_lock:
            for account in self.accounts.values():
                if hmac.compare_digest(account.token, token):
                    return {"uid": account.uid, "name": next(name for name, item in self.accounts.items() if item is account)}
        return None

    def has_uid(self, uid: str) -> bool:
        if self.account_service is not None:
            return self.account_service.has_uid(uid)
        with self.account_lock:
            return any(account.uid == uid for account in self.accounts.values())

    def record(self, method: str, path: str, status: int) -> None:
        key = (method, path, status)
        self.counts[key] = self.counts.get(key, 0) + 1
        print(f"{method} {path} {status} count={self.counts[key]}", file=__import__("sys").stderr)


class BootstrapHTTPServer:
    """Threaded loopback HTTP service with explicit close semantics."""

    def __init__(self, httpd: _Server, thread: threading.Thread):
        self._httpd, self._thread = httpd, thread
        self.host, self.port = httpd.server_address

    @classmethod
    def start_in_thread(cls, manifest_path: Path, port: int = 0, account_service: Any | None = None) -> "BootstrapHTTPServer":
        httpd = _Server(Path(manifest_path), port, account_service)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        return cls(httpd, thread)

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=2)

    def authenticate_token(self, token: str) -> dict[str, str] | None:
        return self._httpd.authenticate_token(token)

    def has_uid(self, uid: str) -> bool:
        return self._httpd.has_uid(uid)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--port", type=int, default=20001)
    args = parser.parse_args()
    try:
        server = BootstrapHTTPServer.start_in_thread(args.manifest, args.port)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"bootstrap server listening on http://{server.host}:{server.port}")
    try:
        server._thread.join()
    except KeyboardInterrupt:
        server.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
