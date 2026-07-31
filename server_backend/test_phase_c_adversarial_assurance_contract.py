"""Phase C adversarial publication, fixture, threat-tree and dependency contracts."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


EYP_ROOT = Path(__file__).resolve().parents[3]
SERVER_ROOT = Path(os.environ.get("MP_OPT_SERVER_ROOT", EYP_ROOT / "MasterplanOptimiserV3 - Server" / "MasterplanOptimiserV3---Server"))
APP_ROOT = Path(os.environ.get("MP_OPT_APP_ROOT", EYP_ROOT / "MasterplanOptimiserV3 - App" / "masterplanOptimiserV3 - App"))
DOCS_ROOT = Path(os.environ.get("MP_OPT_DOCS_ROOT", EYP_ROOT / "MasterplanOptimiserV3 - Docs" / "mp-opt-info"))
FIXTURE = Path(__file__).parent / "fixtures" / "phase_c_security_scanner.json"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from deploy.security.publication_audit import audit_tree, verify_scanner_fixture  # noqa: E402


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)


def test_shared_safe_and_unsafe_scanner_corpus_fails_closed():
    fixture = _json(FIXTURE)
    assert {item["scope"] for item in fixture["unsafe"]} == {"source", "artefact", "evidence", "history"}
    assert len(fixture["unsafe"]) >= 12
    assert verify_scanner_fixture(FIXTURE) == []
    app = _run(["node", "desktop/scripts/audit-publication.js", "--fixture", str(FIXTURE)], APP_ROOT)
    assert app.returncode == 0, app.stderr


def test_current_app_and_server_publishable_trees_pass_hardened_scanners():
    assert audit_tree(SERVER_ROOT) == []
    app = _run(["node", "desktop/scripts/audit-publication.js"], APP_ROOT)
    assert app.returncode == 0, app.stderr


def test_attack_trees_are_connected_to_mitigations_and_real_docs_pages():
    document = _json(DOCS_ROOT / "src/data/security-attack-trees.json")
    assert document["format"] == "masterplan-attack-trees-v1"
    assert len(document["trees"]) >= 3
    for tree in document["trees"]:
        nodes = {node["id"]: node for node in tree["nodes"]}
        assert tree["root"] in nodes
        visited: set[str] = set()

        def visit(identifier: str, active: set[str]):
            assert identifier not in active, f"cycle in {tree['id']} at {identifier}"
            if identifier in visited:
                return
            node = nodes[identifier]
            visited.add(identifier)
            if not node["children"]:
                assert node["mitigations"], f"unmitigated leaf {tree['id']}/{identifier}"
            for mitigation in node["mitigations"]:
                assert mitigation["id"] and mitigation["control"] and mitigation["residual_risk"]
                target = DOCS_ROOT / "src/app" / mitigation["href"].strip("/") / "page.tsx"
                assert target.is_file(), mitigation["href"]
            for child in node["children"]:
                assert child in nodes
                visit(child, active | {identifier})

        visit(tree["root"], set())
        assert visited == set(nodes)
    page = (DOCS_ROOT / "src/app/docs/advanced/threat-models/page.tsx").read_text(encoding="utf-8")
    assert 'role="tree"' in page and "Residual risk:" in page


def test_scanner_disposition_has_no_unowned_finding_or_exception():
    disposition = _json(DOCS_ROOT / "docs/security/scanner-disposition.json")
    assert disposition["format"] == "masterplan-scanner-disposition-v1"
    for category in ("findings", "exceptions"):
        for item in disposition[category]:
            assert item["id"] and item["owner"] and item["rationale"]
    assert disposition["findings"] == []
    assert disposition["exceptions"] == []


def test_docs_dependency_roots_are_remediated_and_backports_are_bounded():
    lock = _json(DOCS_ROOT / "package-lock.json")["packages"]
    assert tuple(map(int, lock["node_modules/next"]["version"].split("."))) >= (16, 2, 11)
    assert tuple(map(int, lock["node_modules/postcss"]["version"].split("."))) >= (8, 5, 18)
    assert tuple(map(int, lock["node_modules/sharp"]["version"].split("."))) >= (0, 35, 0)
    brace_versions = {
        metadata["version"]
        for path, metadata in lock.items()
        if path == "node_modules/brace-expansion" or path.endswith("/node_modules/brace-expansion")
    }
    assert brace_versions <= {"1.1.18", "2.1.4", "5.0.9"}
    assert brace_versions
    security_tests = _run(["node", "--test", "scripts/check-dependencies.test.mjs"], DOCS_ROOT)
    assert security_tests.returncode == 0, security_tests.stderr


def test_docs_diagram_and_link_checker_passes():
    completed = _run(["node", "scripts/check-attack-trees.mjs"], DOCS_ROOT)
    assert completed.returncode == 0, completed.stderr
