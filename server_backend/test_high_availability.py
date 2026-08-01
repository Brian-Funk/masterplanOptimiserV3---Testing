"""External contracts for the current symmetric HA implementation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

from app.core.config import settings
from app.core.ha import HAReadiness, assess_readiness, control_witness_ready
from repo_roots import server_root


class _Result:
    def __init__(self, row):
        self.row = row

    def one_or_none(self):
        return self.row


class _Database:
    def __init__(self, row):
        self.row = row

    def execute(self, _statement):
        return _Result(self.row)


def _configure_ha(monkeypatch) -> None:
    monkeypatch.setattr(settings, "HA_MODE", "ha")
    monkeypatch.setattr(settings, "HA_NODE_ID", "node-a")
    monkeypatch.setattr(settings, "HA_CLUSTER_ID", "test-cluster")
    monkeypatch.setattr(settings, "HA_GENERATION", 3)


def test_readiness_requires_database_cluster_generation_and_holder(monkeypatch):
    _configure_ha(monkeypatch)
    assert assess_readiness(
        _Database((False, True, "test-cluster", 3, "node-a", False))
    ) == HAReadiness(True, "ready")
    assert assess_readiness(
        _Database((True, False, "test-cluster", 3, "node-a", False))
    ).reason == "database-read-only"
    assert assess_readiness(
        _Database((False, True, "other-cluster", 3, "node-a", False))
    ).reason == "cluster-mismatch"
    assert assess_readiness(
        _Database((False, True, "test-cluster", 2, "node-a", False))
    ).reason == "generation-mismatch"
    assert assess_readiness(
        _Database((False, True, "test-cluster", 3, "node-b", False))
    ).reason == "active-node-mismatch"


def test_control_witness_is_fresh_routed_and_holder_bound(tmp_path, monkeypatch):
    _configure_ha(monkeypatch)
    monkeypatch.setattr(settings, "HA_CONTROL_WITNESS_REQUIRED", True)
    monkeypatch.setattr(settings, "HA_CONTROL_WITNESS_MAX_AGE_SECONDS", 60)
    witness_path = tmp_path / "witness.json"
    monkeypatch.setattr(settings, "HA_CONTROL_STATE_PATH", str(witness_path))
    now = datetime.now(timezone.utc)

    def write(**updates) -> None:
        document = {
            "holder_node_id": "node-a",
            "generation": 3,
            "routing_ready": True,
            "observed_at": now.isoformat(),
            "lease_expires_at": (now + timedelta(minutes=2)).isoformat(),
            **updates,
        }
        witness_path.write_text(json.dumps(document), encoding="utf-8")

    write()
    assert control_witness_ready() is True
    write(holder_node_id="node-b")
    assert control_witness_ready() is False
    write(observed_at=(now - timedelta(minutes=2)).isoformat())
    assert control_witness_ready() is False
    write(routing_ready=False)
    assert control_witness_ready() is False


def test_current_ha_topology_and_authoritative_ci_lane_are_committed():
    root = server_root()
    required = (
        "infra/docker-compose.ha.yml",
        "deploy/ha/lease_agent.py",
        "deploy/ha/replication_bundle.py",
        "deploy/ha/receive_replication_bundle.sh",
        "deploy/ha/replication_scheduler.py",
        "deploy/ha/tests/test_lease_fencing.py",
        "deploy/ha/tests/test_replication_bundle.py",
    )
    assert all((root / path).is_file() for path in required)
    workflow = (root / ".github/workflows/server-ci.yml").read_text(encoding="utf-8")
    assert "python -m unittest discover -s deploy/ha/tests -p 'test_*.py' -v" in workflow
    assert not (root / "infra/docker-compose.ha-active.yml").exists()
    assert not (root / "deploy/ha/receive_shared_config.sh").exists()


def test_write_gate_and_management_mutations_fail_closed():
    root = server_root()
    main = (root / "backend/app/main.py").read_text(encoding="utf-8")
    actions = (root / "deploy/management/actions.sh").read_text(encoding="utf-8")
    common = (root / "deploy/management/common.sh").read_text(encoding="utf-8")

    assert '"code": "HA_WRITES_PAUSED"' in main
    assert '"code": "HA_OWNERSHIP_UNVERIFIED"' in main
    assert "require_write_permit(force_refresh=True)" in main
    assert "mp_require_ha_maintenance_window" in actions
    assert "mp_queue_ha_replication" in actions
    assert "mp_require_ha_maintenance_window()" in common
