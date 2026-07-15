"""SSH-only MP-OPT_SERVER management and recovery tooling tests."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess


def _server_root() -> Path:
    """Return the checked-out server repository used by integration tests."""

    return (
        Path(__file__).resolve().parents[3]
        / "MasterplanOptimiserV3 - Server"
        / "MasterplanOptimiserV3---Server"
    )


def _read(relative: str) -> str:
    """Read one management source file as UTF-8."""

    return (_server_root() / relative).read_text(encoding="utf-8")


def test_management_shell_sources_are_syntax_valid():
    """Every SSH management entry point must parse before deployment."""

    root = _server_root()
    scripts = [
        root / "manage.sh",
        root / "configure-production.sh",
        root / "deploy" / "deploy.sh",
        root / "deploy" / "setup-server.sh",
        *sorted((root / "deploy" / "management").glob("*.sh")),
    ]
    result = subprocess.run(
        ["bash", "-n", *map(str, scripts)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_management_entry_point_is_branded_menu_only():
    """The operator receives one branded graphical menu instead of raw commands."""

    entry = _read("manage.sh")
    common = _read("deploy/management/common.sh")

    assert "MP-OPT_SERVER" in entry
    assert "MP-OPT_SERVER" in common
    assert "Brian Funk" in common
    assert "Copyright © %s Brian Funk" in common
    assert 'MP_COPYRIGHT_YEAR="2026"' in common
    assert 'ui_menu "MP-OPT_SERVER"' in entry
    assert "Snapshots and recovery" in entry
    assert "Root administrator recovery" in entry
    assert "Database" in entry
    assert "Logs" in entry
    assert "Maintenance and diagnostics" in entry
    assert "${1:-}" not in entry
    assert 'readlink -f "${BASH_SOURCE[0]}"' in entry


def test_management_launcher_resolves_repository_through_symlink(tmp_path: Path):
    """The installed /usr/local/bin-style symlink must resolve back to the repository."""

    root = _server_root()
    launcher = tmp_path / "bin" / "mp-opt"
    launcher.parent.mkdir()
    launcher.symlink_to(root / "manage.sh")
    command = r"""
        script_path="$(readlink -f "$1")"
        root_dir="$(cd "$(dirname "$script_path")" && pwd)"
        test "$root_dir" = "$2"
        test -f "$root_dir/deploy/management/common.sh"
    """
    result = subprocess.run(
        ["bash", "-Eeuo", "pipefail", "-c", command, "bash", str(launcher), str(root)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_setup_installs_graphical_encrypted_recovery_and_launcher():
    """Fresh VPS setup must install the TUI, encryption tools and friendly launcher."""

    setup = _read("deploy/setup-server.sh")
    deploy = _read("deploy/deploy.sh")

    for package in ("age", "jq", "whiptail"):
        assert package in setup
    assert "/usr/local/bin/mp-opt" in setup
    assert "/usr/local/bin/mp-opt" in deploy
    assert '"$REPO_DIR/manage.sh"' in deploy


def test_production_configurator_delegates_to_guarded_wizard():
    """The compatibility configurator must never retain its old overwrite implementation."""

    wrapper = _read("configure-production.sh")
    actions = _read("deploy/management/actions.sh")

    assert 'exec "$ROOT_DIR/manage.sh"' in wrapper
    assert "An existing .env was detected" in actions
    assert "Configure SMTP activation email now?" in actions
    assert "You can safely skip this" in actions
    assert 'printf \'%s\' "$smtp_token" > "$staging/secrets/smtp_token"' in actions
    assert "SMTP_TOKEN=" not in _read(".env.example")
    assert "SECRET_KEY=" not in _read(".env.example")
    assert "ROOT_BOOTSTRAP_TOKEN=" not in _read(".env.example")
    assert "VAPID_PRIVATE_KEY=" not in _read(".env.example")


def test_redacted_configuration_hides_database_urls_and_secret_keys(tmp_path: Path):
    """Diagnostics must not reveal passwords embedded inside DATABASE_URL."""

    env_file = tmp_path / ".env"
    env_file.write_text(
        "DOMAIN=mp-opt.net\n"
        "DATABASE_URL=postgresql://masterplan:very-secret@db/masterplan\n"
        "POSTGRES_PASSWORD=very-secret\n"
        "SMTP_TOKEN=provider-secret\n",
        encoding="utf-8",
    )
    command = (
        'source deploy/management/common.sh; '
        f'mp_redacted_configuration "{env_file}"'
    )
    result = subprocess.run(
        ["bash", "-c", command],
        cwd=_server_root(),
        check=True,
        capture_output=True,
        text=True,
    )

    assert "very-secret" not in result.stdout
    assert "provider-secret" not in result.stdout
    assert result.stdout.count("<redacted>") == 3
    assert "mp-opt.net" in result.stdout


def test_common_helpers_reject_traversal_and_hash_management_receipts(tmp_path: Path):
    """Snapshot names are path-safe and activity receipts form a SHA-256 chain."""

    environment = os.environ.copy()
    environment.update(
        {
            "MP_ROOT": str(tmp_path),
            "MP_HOME": str(tmp_path / "home"),
            "MP_STATE": str(tmp_path / "state"),
            "MP_SNAPSHOTS": str(tmp_path / "snapshots"),
            "MP_TUI": "ansi",
        }
    )
    command = """
        source deploy/management/common.sh
        mp_initialise_paths
        mp_validate_snapshot_name safe_name-1
        ! mp_validate_snapshot_name ../unsafe
        ! mp_validate_snapshot_name 'unsafe/name'
        mp_audit snapshot.create success database:safe_name-1
        mp_audit snapshot.verify success safe_name-1
        test "$(wc -l < "$MP_AUDIT_FILE")" -eq 2
        first=$(sed -n '1s/|.*//p' "$MP_AUDIT_FILE")
        second_previous=$(sed -n '2s/^[^|]*|[^|]*|[^|]*|[^|]*|[^|]*|[^|]*|//p' "$MP_AUDIT_FILE")
        test "$first" = "$second_previous"
    """
    result = subprocess.run(
        ["bash", "-Eeuo", "pipefail", "-c", command],
        cwd=_server_root(),
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_menu_actions_keep_strict_failure_handling_without_closing_menu(tmp_path: Path):
    """A failed command stops its action but remains recoverable by the dashboard."""

    environment = os.environ.copy()
    environment.update(
        {
            "MP_ROOT": str(tmp_path),
            "MP_HOME": str(tmp_path / "home"),
            "MP_STATE": str(tmp_path / "state"),
            "MP_SNAPSHOTS": str(tmp_path / "snapshots"),
            "MP_TUI": "ansi",
        }
    )
    command = r"""
        source deploy/management/common.sh
        mp_initialise_paths
        unsafe_action() {
            false
            touch "$MP_STATE/should-not-exist"
        }
        mp_run_action unsafe_action
        test ! -e "$MP_STATE/should-not-exist"
        grep -Fq '|menu.action|failed|unsafe_action|' "$MP_AUDIT_FILE"
        touch "$MP_STATE/dashboard-continued"
        test -e "$MP_STATE/dashboard-continued"
    """
    result = subprocess.run(
        ["bash", "-Eeuo", "pipefail", "-c", command],
        cwd=_server_root(),
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_initial_wizard_can_skip_smtp_without_putting_secrets_in_env(tmp_path: Path):
    """First setup creates protected secret files while SMTP remains optional."""

    environment = os.environ.copy()
    environment.update(
        {
            "MP_ROOT": str(tmp_path),
            "MP_HOME": str(tmp_path / "home"),
            "MP_STATE": str(tmp_path / "state"),
            "MP_SNAPSHOTS": str(tmp_path / "snapshots"),
            "MP_TUI": "ansi",
        }
    )
    command = r"""
        source deploy/management/common.sh
        source deploy/management/actions.sh
        mp_initialise_paths
        mp_require_commands() { return 0; }
        mp_compose_validate() { return 0; }
        mp_audit() { return 0; }
        ui_message() { return 0; }
        ui_input() {
            case "$2" in
                "Public application domain") printf '%s\n' 'mp-opt.net' ;;
                "Passkey application name") printf '%s\n' 'Masterplan Access' ;;
                "VAPID contact email") printf '%s\n' 'access@mp-opt.net' ;;
                *) return 1 ;;
            esac
        }
        ui_confirm() {
            case "$1" in
                "Database"|"Review configuration") return 0 ;;
                "Optional activation email"|"Recovery encryption") return 1 ;;
                *) return 1 ;;
            esac
        }
        mp_guided_initial_configuration
        test -s "$MP_ROOT/.env"
        test -s "$MP_ROOT/secrets/secret_key"
        test -s "$MP_ROOT/secrets/vapid_private_key"
        test -s "$MP_ROOT/secrets/root_bootstrap_token"
        test -e "$MP_ROOT/secrets/smtp_token"
        test ! -s "$MP_ROOT/secrets/smtp_token"
        ! grep -Eq '^(SECRET_KEY|ROOT_BOOTSTRAP_TOKEN|VAPID_PRIVATE_KEY|SMTP_TOKEN)=' "$MP_ROOT/.env"
        grep -Fxq 'SMTP_HOST=' "$MP_ROOT/.env"
        test "$(stat -c '%a' "$MP_ROOT/.env")" = 600
        test "$(stat -c '%a' "$MP_ROOT/secrets/secret_key")" = 600
    """
    result = subprocess.run(
        ["bash", "-Eeuo", "pipefail", "-c", command],
        cwd=_server_root(),
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_initial_wizard_refuses_orphaned_non_empty_secrets(tmp_path: Path):
    """Missing .env must not authorise overwriting existing secret material."""

    secrets = tmp_path / "secrets"
    secrets.mkdir()
    existing = secrets / "secret_key"
    existing.write_text("existing-secret", encoding="utf-8")
    environment = os.environ.copy()
    environment.update(
        {
            "MP_ROOT": str(tmp_path),
            "MP_HOME": str(tmp_path / "home"),
            "MP_STATE": str(tmp_path / "state"),
            "MP_SNAPSHOTS": str(tmp_path / "snapshots"),
            "MP_TUI": "ansi",
        }
    )
    command = r"""
        source deploy/management/common.sh
        source deploy/management/actions.sh
        mp_initialise_paths
        ui_error() { printf '%s\n' "$1" >&2; }
        ! mp_guided_initial_configuration
        test ! -e "$MP_ROOT/.env"
        test "$(cat "$MP_ROOT/secrets/secret_key")" = existing-secret
    """
    result = subprocess.run(
        ["bash", "-Eeuo", "pipefail", "-c", command],
        cwd=_server_root(),
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Nothing was overwritten" in result.stderr


def test_legacy_secret_migration_requires_exact_file_match(tmp_path: Path):
    """Legacy env secrets are removed only after byte-for-byte file comparison."""

    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (tmp_path / ".env").write_text(
        "DOMAIN=mp-opt.net\nSECRET_KEY=matching-secret\n",
        encoding="utf-8",
    )
    (secrets / "secret_key").write_text("matching-secret", encoding="utf-8")
    for name in ("vapid_private_key", "root_bootstrap_token", "smtp_token"):
        (secrets / name).write_text("", encoding="utf-8")
    environment = os.environ.copy()
    environment.update(
        {
            "MP_ROOT": str(tmp_path),
            "MP_HOME": str(tmp_path / "home"),
            "MP_STATE": str(tmp_path / "state"),
            "MP_SNAPSHOTS": str(tmp_path / "snapshots"),
            "MP_TUI": "ansi",
        }
    )
    command = r"""
        source deploy/management/common.sh
        source deploy/management/actions.sh
        mp_initialise_paths
        ui_confirm() { return 0; }
        ui_message() { return 0; }
        ui_error() { printf '%s\n' "$1" >&2; }
        mp_recreate_backend() { return 0; }
        mp_audit() { return 0; }
        before=$(sha256sum "$MP_ROOT/secrets/secret_key" | awk '{print $1}')
        mp_migrate_legacy_env_secrets
        after=$(sha256sum "$MP_ROOT/secrets/secret_key" | awk '{print $1}')
        test "$before" = "$after"
        ! grep -q '^SECRET_KEY=' "$MP_ROOT/.env"
        grep -Fxq 'DOMAIN=mp-opt.net' "$MP_ROOT/.env"
    """
    result = subprocess.run(
        ["bash", "-Eeuo", "pipefail", "-c", command],
        cwd=_server_root(),
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_snapshots_are_encrypted_versioned_and_hash_verified():
    """Recovery archives carry internal and external hashes and require age identities."""

    snapshots = _read("deploy/management/snapshots.sh")
    common = _read("deploy/management/common.sh")

    assert "mp-opt-snapshot-v1" in snapshots
    assert "mp-opt-snapshot-receipt-v1" in snapshots
    assert 'age -r "$recipient"' in snapshots
    assert 'age -d -i "$identity_file"' in snapshots
    assert '| tar -tf - > "$members" || return 1' in snapshots
    assert '| tar -tvf - > "$member_types" || return 1' in snapshots
    assert "sort \"$list_file\" | uniq -d" in snapshots
    assert '| tar -C "$destination" -xf - || return 1' in snapshots
    assert "sha256sum" in snapshots
    assert "pg_restore --list" in snapshots
    assert 'verification: "encrypted"' in snapshots
    assert '.verification = "deep-verified"' in snapshots
    assert "/dev/shm" in common
    assert "AGE-SECRET-KEY-1" in common


def test_destructive_actions_require_deep_snapshot_and_exact_phrase_first():
    """Root reset, wipe, domain and rotations cannot mutate before guarded recovery."""

    actions = _read("deploy/management/actions.sh")

    expectations = {
        "mp_reset_root_admin()": "RESET ROOT ADMIN",
        "mp_wipe_database()": "WIPE DATABASE",
        "mp_change_domain()": "CHANGE DOMAIN TO $new_domain",
        "mp_rotate_database_password()": "ROTATE DATABASE PASSWORD",
        "mp_rotate_application_secret()": "ROTATE APPLICATION SECRET",
        "mp_rotate_vapid()": "ROTATE VAPID",
    }
    for marker, phrase in expectations.items():
        start = actions.index(marker)
        next_function = actions.find("\n# ", start + len(marker))
        body = actions[start : next_function if next_function != -1 else None]
        assert "mp_prepare_guard_snapshot" in body
        assert phrase in body
        assert body.index("mp_prepare_guard_snapshot") < body.index(phrase)


def test_root_reset_is_authentication_scoped_and_domain_change_preserves_docs():
    """Root recovery preserves other users while RP changes explicitly reset all credentials."""

    actions = _read("deploy/management/actions.sh")
    root_start = actions.index("mp_reset_root_admin()")
    root_end = actions.index("mp_disable_root_bootstrap()")
    root_body = actions[root_start:root_end]
    domain_start = actions.index("mp_change_domain()")
    domain_end = actions.index("mp_rotate_database_password()")
    domain_body = actions[domain_start:domain_end]

    assert "DELETE FROM webauthn_credentials WHERE user_id = root_id" in root_body
    assert "DELETE FROM auth_sessions WHERE user_id = root_id" in root_body
    assert "DELETE FROM users" not in root_body
    assert "DELETE FROM webauthn_credentials;" in domain_body
    assert "UPDATE users SET is_activated = FALSE" in domain_body
    assert "info.mp-opt.net remains unchanged" in domain_body
    assert "info\\.mp-opt\\.net" in domain_body


def test_database_wipe_recreates_schema_then_applies_committed_migrations():
    """A clean database must reach the same migrated schema as an upgraded one."""

    actions = _read("deploy/management/actions.sh")
    start = actions.index("mp_wipe_database()")
    end = actions.index("mp_change_domain()")
    body = actions[start:end]

    create_database = body.index("createdb -U masterplan masterplan")
    start_backend = body.index("up -d --no-deps --force-recreate backend")
    apply_migrations = body.index("mp_apply_migrations")
    recreate_backend = body.index("mp_recreate_backend", apply_migrations)
    assert create_database < start_backend < apply_migrations < recreate_backend
    assert 'mp_guard_rollback "Fresh database schema migration failed."' in body


def test_restore_verifies_then_creates_verified_rollback_before_apply():
    """Snapshot restore must prove both selected and rollback archives before mutation."""

    snapshots = _read("deploy/management/snapshots.sh")
    start = snapshots.index("mp_snapshot_restore_interactive()")
    end = snapshots.index("mp_snapshot_delete_interactive()")
    body = snapshots[start:end]

    first_verify = body.index('mp_snapshot_verify_path "$selected"')
    pre_create = body.index("mp_snapshot_create full")
    pre_verify = body.index('mp_snapshot_verify_path "$pre_snapshot"')
    apply_selected = body.index('mp_snapshot_apply "$selected"')
    assert first_verify < pre_create < pre_verify < apply_selected
    assert 'mp_snapshot_apply "$pre_snapshot"' in body
