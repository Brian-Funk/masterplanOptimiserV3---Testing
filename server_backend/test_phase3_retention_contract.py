"""Independent Phase 3 Server and Desktop retention-contract checks."""

from datetime import date, datetime, timedelta, timezone
import os
from pathlib import Path

from app.core import retention
from app.models.deletion import DeletionCase, DesktopDeletionWorkOrder
from app.models.server_setting import ServerSetting
from server_backend.conftest import create_test_event


def _unsigned_case_stub(db, event, **kwargs):
    """Stand in only for filesystem signing in the external SQLite suite."""

    case = DeletionCase(
        case_type="event_erasure",
        initiation_reason=kwargs["initiation_reason"],
        event_purge_key=event.evidence_id,
        instance_id="11111111-1111-4111-8111-111111111111",
        event_evidence_id=event.evidence_id,
        subject_evidence_id=event.evidence_id,
        state="submitted",
        normal_response_due_at=kwargs["now"] + timedelta(days=30),
    )
    db.add(case)
    db.flush()
    return case


def test_grace_boundary_is_exact_restart_safe_and_requires_root_decision(
    db, monkeypatch
):
    monkeypatch.setattr(retention, "create_event_erasure_case", _unsigned_case_stub)
    db.add(ServerSetting(key="event_purge_grace_days", value="3"))
    event, _secret = create_test_event(db, name="Synthetic cross-repository event")
    event.end_date = date(2026, 8, 10)
    retention.materialise_event_purge_deadline(event, db, force=True)
    db.commit()
    due = datetime(2026, 8, 14, tzinfo=timezone.utc)

    retention.run_retention_cycle(db, now=due - timedelta(microseconds=1))
    assert db.query(DeletionCase).count() == 0
    retention.run_retention_cycle(db, now=due)
    retention.run_retention_cycle(db, now=due + timedelta(hours=1))

    case = db.query(DeletionCase).one()
    assert case.initiation_reason == "retention_schedule"
    assert case.state == "submitted"
    assert case.decision_at is None
    assert case.access_revoked_at is None
    assert db.query(DesktopDeletionWorkOrder).count() == 0
    assert event.purge_case_request_id == case.request_id


def test_server_work_order_contract_matches_transactional_desktop_event_erasure():
    app_root = Path(os.environ["MP_OPT_APP_ROOT"])
    desktop_service = (
        app_root / "backend/app/core/desktop_deletion.py"
    ).read_text(encoding="utf-8")
    server_service = Path(retention.__file__).resolve().parents[1] / "core/deletion_cases.py"
    server_contract = server_service.read_text(encoding="utf-8")

    assert 'operation="delete_event" if case.case_type == "event_erasure"' in server_contract
    assert 'elif operation == "delete_event" and work_order.get("subject_ref") is None:' in desktop_service
    assert "delete_event_scoped_data(db, event.id)" in desktop_service
    assert "DesktopDeletionOutbox" in desktop_service


def test_retention_inventory_distinguishes_automation_from_attestation():
    inventory = {
        row["record_class"]: row["mechanism"]
        for row in retention.RETENTION_INVENTORY
    }
    assert inventory["events"] == "scheduled_signed_workflow"
    assert inventory["recovery_packages"] == "controller_attested_workflow"
    assert inventory["evidence_ledger"] == "controller_repository_policy"
    assert not inventory["recovery_packages"].startswith("scheduled_")
