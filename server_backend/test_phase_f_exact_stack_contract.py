"""Independent contracts for the Phase F exact-stack qualification."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

from repo_roots import app_root, optional_docs_root, server_root


EYP_ROOT = Path(__file__).resolve().parents[3]
APP_ROOT = app_root()
SERVER_ROOT = server_root()
DOCS_ROOT = optional_docs_root()
TESTING_ROOT = Path(__file__).resolve().parents[1]


def _runner_module():
    path = TESTING_ROOT / "tools" / "phase_f_exact_stack.py"
    spec = importlib.util.spec_from_file_location("phase_f_exact_stack", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load Phase F runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_plan_covers_every_phase_f_lane_and_boundary() -> None:
    plan = json.loads(
        (TESTING_ROOT / "tools" / "phase_f_exact_stack_plan.json").read_text(encoding="utf-8")
    )
    coverage = {item for lane in plan["lanes"] for item in lane["covers"]}
    for required in (
        "bootstrap", "controller configuration", "governance publication", "event creation",
        "current-format Desktop publication", "participant access", "organiser access",
        "optional public schedule", "offline lifecycle", "encrypted synthetic backup",
        "verified restore", "account deletion", "event deletion", "evidence export",
        "temporary evidence Git import", "human-readable summary", "converter dry run",
        "conversion", "semantic comparison", "rollback", "no Desktop integration",
        "exactly-once instance key", "root passkey exact action",
        "controller external custody", "Desktop processor-only key generation",
        "OS credential custody", "controller exclusion", "HA fingerprint continuity",
        "governance trust gate",
    ):
        assert required in coverage
    exclusions = "\n".join(plan["exclusions"])
    for prohibited in (
        "runtime legacy compatibility", "automatic startup migration",
        "converter UI or user-facing import flow", "dual-read or dual-write behaviour",
        "legacy-data synchronisation", "ongoing legacy-format support",
        "protected data or live backups", "deployment or release",
        "real controller or processor key ceremony",
        "controller or processor private keys in Server",
        "writes to Evidence or Evidence-Public",
    ):
        assert prohibited in exclusions


def test_phase_f_sources_are_separate_and_documented() -> None:
    converter = (APP_ROOT / "tools" / "one_off" / "convert_current_desktop_v2.py").read_text(
        encoding="utf-8"
    )
    server_test = (SERVER_ROOT / "server_backend" / "test_phase_f_exact_stack.py").read_text(
        encoding="utf-8"
    )
    server_doc = (SERVER_ROOT / "docs" / "exact-stack-qualification.md").read_text(
        encoding="utf-8"
    )
    public_doc = None
    if DOCS_ROOT is not None:
        public_doc = (
            DOCS_ROOT / "src" / "app" / "docs" / "desktop" / "import-export" / "page.tsx"
        ).read_text(encoding="utf-8")
    desktop_core = (APP_ROOT / "backend" / "app" / "core" / "operator_evidence.py").read_text(
        encoding="utf-8"
    )
    server_trust = (SERVER_ROOT / "backend" / "app" / "api" / "v1" / "evidence_keys.py").read_text(
        encoding="utf-8"
    )
    key_doc = (SERVER_ROOT / "docs" / "key-custody-and-trust.md").read_text(encoding="utf-8")

    assert 'OPERATOR_TOOL_SCOPE = "separate-temporary-one-time-converter"' in converter
    assert "def dry_run(" in converter and "def rollback(" in converter
    assert "contract_version" in server_test and "no_legacy_runtime_fallback" in server_test
    for document in (server_doc, *([public_doc] if public_doc is not None else [])):
        assert "separate" in document
        assert "startup migration" in document
        assert "dual-read" in document
        assert "ongoing" in document and "format" in document
    assert 'PROCESSOR_ROLE = "processor"' in desktop_core
    assert "generate_key" in desktop_core and '"controller"' not in desktop_core
    assert "root-authorisation/complete" in server_trust
    assert "possession_proof_sha256" in server_trust
    for role in ("instance", "root_passkey", "controller", "processor"):
        assert f"`{role}`" in key_doc


def test_runner_records_exact_repositories_and_lane_results(tmp_path, monkeypatch) -> None:
    runner = _runner_module()
    roots = {name: tmp_path / name for name in ("app", "server", "testing", "docs")}
    for root in roots.values():
        (root / ".git").mkdir(parents=True)
    plan = {
        "format": "masterplan-phase-f-exact-stack-plan-v1",
        "roadmap_version": "test",
        "requirements": ["INTEGRATION-11"],
        "repositories": {
            name: {"environment": f"PHASE_F_{name.upper()}", "default_relative": name}
            for name in roots
        },
        "lanes": [{
            "id": "synthetic-pass", "repository": "testing", "cwd": ".",
            "command": ["python", "-c", "print('synthetic pass')"], "covers": ["test"],
        }],
        "exclusions": ["real data"],
    }
    plan_path = tmp_path / "plan.json"
    output = tmp_path / "receipt.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    for name, root in roots.items():
        monkeypatch.setenv(f"PHASE_F_{name.upper()}", str(root))

    def fake_git(_root, *arguments):
        if arguments == ("status", "--porcelain"):
            return ""
        if arguments == ("rev-parse", "HEAD"):
            return "a" * 40
        if arguments == ("rev-parse", "HEAD^{tree}"):
            return "b" * 40
        if arguments == ("remote", "get-url", "origin"):
            return "https://example.invalid/repository.git"
        raise AssertionError(arguments)

    monkeypatch.setattr(runner, "_git", fake_git)
    receipt = runner.execute(plan_path, output, eyp_root=tmp_path)

    assert receipt["passed"] is True
    assert set(receipt["repositories"]) == set(roots)
    assert all(item["head_sha"] == "a" * 40 for item in receipt["repositories"].values())
    assert receipt["lanes"][0]["passed"] is True
    assert json.loads(output.read_text(encoding="utf-8"))["plan_sha256"] == runner._sha256(plan_path)
