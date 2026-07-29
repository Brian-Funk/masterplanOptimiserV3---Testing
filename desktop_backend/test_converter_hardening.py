"""External regressions for the standalone, copy-only Desktop converter."""

from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest


_APP_ROOT = (
    Path(__file__).resolve().parents[3]
    / "MasterplanOptimiserV3 - App"
    / "masterplanOptimiserV3 - App"
)


def _converter_module():
    converter_path = _APP_ROOT / "tools" / "one_off" / "convert_current_desktop_v2.py"
    spec = importlib.util.spec_from_file_location("external_desktop_converter", converter_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the Desktop converter")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_converter_rejects_a_source_with_a_live_wal(tmp_path: Path) -> None:
    converter = _converter_module()
    source_path = tmp_path / "source.db"
    writer = sqlite3.connect(source_path)
    try:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        writer.execute("INSERT INTO events VALUES (1, 'WAL-only event')")
        writer.commit()
        assert Path(f"{source_path}-wal").exists()

        with pytest.raises(RuntimeError, match="SQLite companion files"):
            converter._source_connection(source_path)
    finally:
        writer.close()


def test_converter_publication_removes_partial_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    converter = _converter_module()
    temporary = [tmp_path / f"temporary-{index}" for index in range(3)]
    final = [tmp_path / f"final-{index}" for index in range(3)]
    for index, path in enumerate(temporary):
        path.write_text(str(index), encoding="utf-8")

    real_link = converter.os.link
    calls = 0

    def fail_second_move(source: Path, target: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected archive publication failure")
        real_link(source, target)

    monkeypatch.setattr(converter.os, "link", fail_second_move)

    with pytest.raises(OSError, match="injected archive publication failure"):
        converter._publish_outputs(list(zip(temporary, final)))

    assert calls == 2
    assert not any(path.exists() for path in final)


def test_converter_publication_preserves_a_preexisting_destination(
    tmp_path: Path,
) -> None:
    converter = _converter_module()
    temporary = [tmp_path / f"temporary-{index}" for index in range(3)]
    final = [tmp_path / f"final-{index}" for index in range(3)]
    for index, path in enumerate(temporary):
        path.write_text(str(index), encoding="utf-8")
    final[1].write_text("preserve me", encoding="utf-8")

    with pytest.raises(FileExistsError):
        converter._publish_outputs(list(zip(temporary, final)))

    assert not final[0].exists()
    assert final[1].read_text(encoding="utf-8") == "preserve me"
    assert not final[2].exists()


def test_converter_accounts_for_deduplicated_and_rejected_typed_fields() -> None:
    converter = _converter_module()
    source = sqlite3.connect(":memory:")
    target = sqlite3.connect(":memory:")
    source.row_factory = sqlite3.Row
    target.row_factory = sqlite3.Row
    try:
        source.execute(
            "CREATE TABLE persons "
            "(id INTEGER PRIMARY KEY, event_id INTEGER NOT NULL, global_data TEXT)"
        )
        source.execute(
            "INSERT INTO persons VALUES (?, ?, ?)",
            (
                1,
                7,
                json.dumps({
                    "capabilities": ["chair", "chair", "unknown"],
                    "unavailabilities": [{
                        "starts_at": "2026-08-01T10:00:00",
                        "ends_at": "2026-08-01T11:00:00",
                    }],
                    "private_note": "archive only",
                }),
            ),
        )
        target.executescript(
            """
            CREATE TABLE capabilities (id INTEGER PRIMARY KEY, machine_name TEXT NOT NULL);
            CREATE TABLE person_capabilities (
                person_id INTEGER NOT NULL, capability_id INTEGER NOT NULL
            );
            CREATE TABLE person_unavailability (
                event_id INTEGER NOT NULL, person_id INTEGER NOT NULL,
                starts_at TEXT NOT NULL, ends_at TEXT NOT NULL
            );
            """
        )
        target.execute("INSERT INTO capabilities VALUES (1, 'chair')")
        target.execute("INSERT INTO person_capabilities VALUES (1, 1)")

        audit = converter._map_person_operational_fields(source, target, "a" * 64)

        assert audit["capability_links_added"] == 0
        assert audit["capability_links_already_present"] == 1
        assert audit["unavailability_intervals_added"] == 1
        assert audit["archived_only_global_fields"] == 1
        assert any(
            item["code"] == "unknown_capability_reference"
            for item in audit["rejected_records"]
        )
    finally:
        source.close()
        target.close()
