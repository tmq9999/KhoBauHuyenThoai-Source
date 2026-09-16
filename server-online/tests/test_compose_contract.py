"""Validate the Compose model using the actual CLI; no Docker engine needed."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).parents[2]


def compose_cli():
    configured = os.environ.get("KBHT_COMPOSE_BIN")
    if configured:
        return [configured]
    local = ROOT / "work/m1-env/download/docker-compose-v5.5.1.exe"
    if local.is_file():
        return [str(local)]
    standalone = shutil.which("docker-compose")
    if standalone:
        return [standalone]
    docker = shutil.which("docker")
    if docker:
        return [docker, "compose"]
    pytest.fail("Set KBHT_COMPOSE_BIN to a Compose CLI for configuration validation")


def render_compose(env):
    return subprocess.run(compose_cli() + ["--project-directory", str(ROOT), "-f", str(ROOT / "compose.yaml"),
                                         "--profile", "test", "config", "--format", "json"],
                          capture_output=True, text=True, env=env, timeout=30)


@pytest.fixture()
def compose_environment(tmp_path):
    password = tmp_path / "postgres.txt"
    password.write_text("compose-test-password-not-a-real-secret", encoding="ascii")
    acl = tmp_path / "redis.acl"
    acl.write_text("user default off\n", encoding="ascii")
    env = dict(os.environ)
    env.update(KBHT_POSTGRES_PASSWORD_FILE=str(password), KBHT_REDIS_ACL_FILE=str(acl), COMPOSE_DISABLE_ENV_FILE="true")
    return env


def test_compose_models_loopback_dev_test_isolation_and_pg18_volume(compose_environment):
    result = render_compose(compose_environment)
    assert result.returncode == 0, result.stderr
    model = json.loads(result.stdout)
    assert set(model["services"]) == {"postgres", "postgres-test", "redis"}
    for name, database, port in (("postgres", "kbht_dev", "25433"), ("postgres-test", "kbht_test", "25434")):
        service = model["services"][name]
        assert service["environment"]["POSTGRES_DB"] == database
        assert service["environment"]["POSTGRES_PASSWORD_FILE"] == "/run/secrets/postgres_password"
        assert service["ports"][0]["host_ip"] == "127.0.0.1"
        assert service["ports"][0]["published"] == port
        assert service["ports"][0]["target"] == 5432
        assert service["volumes"][0]["target"] == "/var/lib/postgresql"
    assert model["services"]["postgres"]["volumes"][0]["source"] != model["services"]["postgres-test"]["volumes"][0]["source"]
    for service in model["services"].values():
        assert re.fullmatch(r"(?:postgres|redis):[0-9]+\.[0-9]+(?:\.[0-9]+)?-bookworm@sha256:[0-9a-f]{64}", service["image"])
        assert service["healthcheck"]["test"]
        assert not service.get("privileged", False)
        assert service.get("network_mode") != "host"
    assert "compose-test-password-not-a-real-secret" not in result.stdout


def test_redis_uses_acl_secret_and_no_durable_game_data(compose_environment):
    result = render_compose(compose_environment)
    assert result.returncode == 0, result.stderr
    redis = json.loads(result.stdout)["services"]["redis"]
    assert redis["ports"][0]["host_ip"] == "127.0.0.1"
    assert redis["ports"][0]["published"] == "26379"
    assert "--aclfile" in redis["command"]
    assert "/run/secrets/redis_acl" in redis["command"]
    assert {secret["source"] for secret in redis["secrets"]} == {"redis_acl"}
    assert redis["command"][redis["command"].index("--save") + 1] == ""
    assert redis["command"][redis["command"].index("--appendonly") + 1] == "no"
    assert not redis.get("volumes")


@pytest.mark.parametrize("missing", ["KBHT_POSTGRES_PASSWORD_FILE", "KBHT_REDIS_ACL_FILE"])
def test_compose_fails_closed_without_secret_path(compose_environment, missing):
    compose_environment.pop(missing)
    result = render_compose(compose_environment)
    assert result.returncode != 0
    assert missing in result.stderr
