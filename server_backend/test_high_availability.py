"""Tests for fail-closed active-passive server behaviour."""

import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess

from app.core.config import settings
from app.core.ha import HAReadiness, assess_readiness, control_witness_ready
from starlette.requests import Request


def _server_root() -> Path:
    """Return the server repository used by the integration tests."""

    return (
        Path(__file__).resolve().parents[3]
        / "MasterplanOptimiserV3 - Server"
        / "MasterplanOptimiserV3---Server"
    )


class _Result:
    """Minimal SQLAlchemy result stand-in for readiness unit tests."""

    def __init__(self, row):
        self.row = row

    def one_or_none(self):
        """Return the configured result row."""

        return self.row


class _Database:
    """Minimal database session stand-in for one readiness query."""

    def __init__(self, row):
        self.row = row

    def execute(self, _statement):
        """Return the predefined readiness row."""

        return _Result(self.row)


def _configure_ha(monkeypatch, role: str = "active") -> None:
    """Set a complete in-process HA identity for one test."""

    monkeypatch.setattr(settings, "HA_MODE", "ha")
    monkeypatch.setattr(settings, "HA_ROLE", role)
    monkeypatch.setattr(settings, "HA_NODE_ID", "node-a")
    monkeypatch.setattr(settings, "HA_CLUSTER_ID", "test-cluster")
    monkeypatch.setattr(settings, "HA_GENERATION", 3)


def test_readiness_requires_role_database_cluster_and_generation(monkeypatch):
    """Only the durable writable active generation may report ready."""

    _configure_ha(monkeypatch)
    assert assess_readiness(
        _Database((False, True, "test-cluster", 3, "node-a", False))
    ) == HAReadiness(True, "ready")
    assert assess_readiness(
        _Database((True, False, "test-cluster", 3, "node-a", False))
    ).reason == "database-read-only"
    assert assess_readiness(
        _Database((False, True, "test-cluster", 2, "node-a", False))
    ).reason == "generation-mismatch"
    assert assess_readiness(
        _Database((False, True, "other-cluster", 3, "node-a", False))
    ).reason == "cluster-mismatch"
    assert assess_readiness(
        _Database((False, True, "test-cluster", 3, "node-b", False))
    ).reason == "active-node-mismatch"
    assert assess_readiness(
        _Database((False, True, "test-cluster", 3, "node-a", True))
    ).reason == "maintenance"


def test_control_witness_is_identity_generation_and_freshness_bound(monkeypatch, tmp_path):
    """A stale former active cannot rely on its old local database generation."""

    witness = tmp_path / "ha-control.json"
    _configure_ha(monkeypatch)
    monkeypatch.setattr(settings, "HA_CONTROL_WITNESS_REQUIRED", True)
    monkeypatch.setattr(settings, "HA_CONTROL_STATE_PATH", str(witness))
    monkeypatch.setattr(settings, "HA_CONTROL_WITNESS_MAX_AGE_SECONDS", 90)

    def write(**changes):
        value = {
            "node_id": "node-a",
            "generation": 3,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "node_pool_is_first": True,
            "load_balancer_enabled": True,
        }
        value.update(changes)
        witness.write_text(json.dumps(value), encoding="utf-8")

    write()
    assert control_witness_ready() is True
    write(node_pool_is_first=False)
    assert control_witness_ready() is False
    write(generation=2)
    assert control_witness_ready() is False
    write(observed_at=(datetime.now(timezone.utc) - timedelta(seconds=91)).isoformat())
    assert control_witness_ready() is False


def test_readiness_endpoint_is_minimal_and_never_cacheable(monkeypatch):
    """The load-balancer probe exposes no topology or database detail."""

    import app.main as main_module

    _configure_ha(monkeypatch)

    class _Session:
        def close(self):
            """Close the test session."""

    monkeypatch.setattr(main_module, "SessionLocal", _Session)
    monkeypatch.setattr(main_module, "assess_readiness", lambda _db: HAReadiness(True, "ready"))
    monkeypatch.setattr(main_module, "record_heartbeat", lambda _db: None)
    response = asyncio.run(main_module.ha_ready())
    assert response.status_code == 200
    assert response.body == b"ready\n"
    assert response.headers["cache-control"] == "no-store"

    monkeypatch.setattr(main_module, "assess_readiness", lambda _db: HAReadiness(False, "secret-reason"))
    response = asyncio.run(main_module.ha_ready())
    assert response.status_code == 503
    assert response.body == b"unavailable\n"
    assert b"secret-reason" not in response.body


def test_write_gate_rejects_every_mutation_on_standby(monkeypatch):
    """A standby rejects even token-authenticated public write paths."""

    import app.main as main_module

    _configure_ha(monkeypatch, role="standby")

    class _Session:
        def close(self):
            """Close the test session."""

    monkeypatch.setattr(main_module, "SessionLocal", _Session)
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/activation/validate",
            "headers": [],
            "query_string": b"",
            "server": ("localhost", 443),
            "client": ("127.0.0.1", 12345),
            "scheme": "https",
        }
    )
    response = asyncio.run(
        main_module.enforce_active_writer(request, lambda _request: None)
    )
    assert response.status_code == 503
    assert response.body == b'{"detail":"This node is not available for writes."}'
    assert response.headers["retry-after"] == "5"


def test_ha_deployment_is_opt_in_and_standby_omits_backend():
    """Existing servers stay standalone and replicas do not run FastAPI."""

    root = _server_root()
    common = (root / "deploy/management/common.sh").read_text(encoding="utf-8")
    active = (root / "infra/docker-compose.ha-active.yml").read_text(encoding="utf-8")
    standby = (root / "infra/docker-compose.ha-standby.yml").read_text(encoding="utf-8")
    caddy = (root / "infra/Caddyfile.standby").read_text(encoding="utf-8")
    assert "export HA_MODE=standalone HA_ROLE=standalone" in common
    assert "docker-compose.ha-active.yml" in common
    assert "docker-compose.ha-standby.yml" in common
    assert 'profiles: ["active-only"]' in standby
    assert 'respond "unavailable\\n" 503' in caddy
    assert "max_wal_senders" not in active


def test_ha_migration_and_postgres_policy_are_committed():
    """Cluster generation and bounded WAL retention are reproducible."""

    root = _server_root()
    migration = (root / "deploy/migrations/20260716_high_availability.sql").read_text(
        encoding="utf-8"
    )
    postgres = (root / "infra/postgres/ha-postgresql.conf").read_text(encoding="utf-8")
    hba = (root / "infra/postgres/pg_hba.ha.conf").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS ha_cluster_state" in migration
    assert "CREATE TABLE IF NOT EXISTS ha_node_heartbeats" in migration
    assert "max_wal_senders = 5" in postgres
    assert "max_replication_slots = 2" in postgres
    assert "wal_keep_size = '1GB'" in postgres
    assert "max_slot_wal_keep_size = '2GB'" in postgres
    assert "10.77.0.0/30" in hba
    assert "0.0.0.0/0               reject" in hba


def test_ha_management_blocks_standby_destructive_actions():
    """Recovery and credential-changing workflows require the active role."""

    root = _server_root()
    actions = (root / "deploy/management/actions.sh").read_text(encoding="utf-8")
    snapshots = (root / "deploy/management/snapshots.sh").read_text(encoding="utf-8")
    ha = (root / "deploy/management/ha.sh").read_text(encoding="utf-8")
    for function in (
        "mp_reset_root_admin",
        "mp_wipe_database",
        "mp_change_domain",
        "mp_rotate_database_password",
        "mp_rotate_application_secret",
        "mp_rotate_vapid",
    ):
        body = actions.split(f"{function}() {{", 1)[1].split("\n}", 1)[0]
        assert "mp_require_active_or_standalone" in body
    restore = snapshots.split("mp_snapshot_restore_interactive() {", 1)[1].split("\n}", 1)[0]
    assert "mp_require_active_or_standalone" in restore
    assert "fence-unproven" in ha
    assert "PROMOTE $HA_NODE_ID GENERATION $next_generation" in ha
    assert "Automatic promotion is intentionally locked" in ha
    assert "ENABLE AUTOMATIC FAILOVER" not in ha


def test_ha_shell_and_python_entry_points_parse():
    """Every unattended HA entry point must parse before VPS installation."""

    root = _server_root()
    shell_scripts = sorted((root / "deploy/ha").glob("*.sh"))
    shell_result = subprocess.run(
        ["bash", "-n", *map(str, shell_scripts)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert shell_result.returncode == 0, shell_result.stderr
    python_scripts = sorted((root / "deploy/ha").glob("*.py"))
    python_result = subprocess.run(
        ["python3", "-m", "py_compile", *map(str, python_scripts)],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPYCACHEPREFIX": "/tmp/mp-opt-ha-tests"},
    )
    assert python_result.returncode == 0, python_result.stderr


def test_standby_bootstrap_persists_replication_authentication_safely():
    """Streaming authentication must survive the transient base-backup container."""

    root = _server_root()
    ha = (root / "deploy/management/ha.sh").read_text(encoding="utf-8")
    assert "postgresql.auto.conf" in ha
    assert "chmod 600 /var/lib/postgresql/data/postgresql.auto.conf" in ha
    assert "application_name=%s" in ha
    assert "unset password" in ha
    assert "receive_replication_password.sh" in ha
    assert "INSTALLED:$local_hash" in ha


def test_shared_configuration_receiver_is_atomic_and_hash_verified():
    """The standby rolls back partial shared-secret installation attempts."""

    root = _server_root()
    receiver = (root / "deploy/ha/receive_shared_config.sh").read_text(
        encoding="utf-8"
    )
    assert "tar -tf" in receiver
    assert "Unsafe shared configuration archive member" in receiver
    assert "sha256sum -c shared.sha256" in receiver
    assert 'role" = "standby"' in receiver
    assert 'installed=0' in receiver
    assert 'cp -a "$backup/.env"' in receiver


def test_control_plane_witness_and_automatic_snapshots_are_hardened():
    """A stale node fails closed while recovery archives remain bounded."""

    root = _server_root()
    active = (root / "infra/docker-compose.ha-active.yml").read_text(encoding="utf-8")
    control = (root / "deploy/ha/control_witness.py").read_text(encoding="utf-8")
    snapshots = (root / "deploy/ha/automatic_snapshots.sh").read_text(encoding="utf-8")
    setup = (root / "deploy/setup-server.sh").read_text(encoding="utf-8")
    assert 'HA_CONTROL_WITNESS_REQUIRED: "true"' in active
    assert 'node_pool_is_first' in control
    assert 'temporary.replace(STATUS_PATH)' in control
    assert "ha-auto-hourly" in snapshots and " 24" in snapshots
    assert "ha-auto-daily" in snapshots and " 14" in snapshots
    assert "ha-auto-weekly" in snapshots and " 8" in snapshots
    assert "sha256sum" in snapshots and "rsync" in snapshots
    for package in ("wireguard-tools", "rsync", "python3-openstackclient"):
        assert package in setup
