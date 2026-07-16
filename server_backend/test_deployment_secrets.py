"""Production deployment secret provisioning tests."""
from pathlib import Path


def _server_root() -> Path:
    """Return the checked-out server repository root used by external tests."""
    return (
        Path(__file__).resolve().parents[3]
        / "MasterplanOptimiserV3 - Server"
        / "MasterplanOptimiserV3---Server"
    )


def test_deploy_provisions_required_root_bootstrap_secret():
    """Deploy must create Compose's bootstrap bind source when it is absent."""
    deploy_script = (_server_root() / "deploy" / "deploy.sh").read_text(
        encoding="utf-8",
    )

    assert 'if [ ! -e "secrets/root_bootstrap_token" ]; then' in deploy_script
    assert "'^ROOT_BOOTSTRAP_TOKEN='" in deploy_script
    assert '[[ "$ROOT_BOOTSTRAP_TOKEN" == CHANGE_ME* ]]' in deploy_script
    assert (
        'printf "%s" "$ROOT_BOOTSTRAP_TOKEN" > secrets/root_bootstrap_token'
        in deploy_script
    )
    assert (
        "chmod 600 secrets/secret_key secrets/vapid_private_key "
        "secrets/root_bootstrap_token secrets/smtp_token"
        in deploy_script
    )


def test_deploy_preserves_an_empty_bootstrap_secret():
    """An existing empty secret must continue to mean bootstrap is disabled."""
    deploy_script = (_server_root() / "deploy" / "deploy.sh").read_text(
        encoding="utf-8",
    )

    assert 'if [ ! -e "secrets/root_bootstrap_token" ]; then' in deploy_script
    assert 'if [ ! -s "secrets/root_bootstrap_token" ]; then' not in deploy_script


def test_smtp_token_is_provisioned_as_an_optional_docker_secret():
    """SMTP credentials must be mounted from a protected file, never `.env`."""

    root = _server_root()
    deploy_script = (root / "deploy" / "deploy.sh").read_text(encoding="utf-8")
    compose = (root / "infra" / "docker-compose.prod.yml").read_text(
        encoding="utf-8",
    )
    example_env = (root / ".env.example").read_text(encoding="utf-8")

    assert ': > secrets/smtp_token' in deploy_script
    assert "secrets/smtp_token" in deploy_script
    assert "smtp_token:" in compose
    assert "file: ../secrets/smtp_token" in compose
    assert "SMTP_TOKEN=" not in example_env


def test_activation_email_brand_and_qr_assets_are_packaged_predictably():
    """Production must use the approved mail identity and deterministic artwork."""

    root = _server_root()
    example_env = (root / ".env.example").read_text(encoding="utf-8")
    management_actions = (root / "deploy" / "management" / "actions.sh").read_text(
        encoding="utf-8",
    )
    dockerfile = (root / "infra" / "Dockerfile").read_text(encoding="utf-8")

    assert "SMTP_FROM_NAME=Masterplan Access" in example_env
    assert 'smtp_from_name="Masterplan Access"' in management_actions
    assert "fonts-dejavu-core" in dockerfile
    assert (
        "COPY web/public/logo_normal.png /app/app/assets/logo_normal.png"
        in dockerfile
    )


def test_secret_material_is_excluded_from_git_and_docker_context():
    """Local credentials and backups must not enter commits or build layers."""

    root = _server_root()
    gitignore = (root / ".gitignore").read_text(encoding="utf-8")
    dockerignore = (root / ".dockerignore").read_text(encoding="utf-8")

    for ignored in (".env.*", "secrets/"):
        assert ignored in gitignore
        assert ignored in dockerignore


def test_blank_database_base_schema_runs_before_dynamic_migrations():
    """Deployment must initialise a blank schema before ordered migrations."""

    root = _server_root()
    deploy_script = (root / "deploy" / "deploy.sh").read_text(encoding="utf-8")
    common = (root / "deploy" / "management" / "common.sh").read_text(
        encoding="utf-8",
    )
    backend_build = '"${MP_COMPOSE[@]}" build backend'
    base_schema = "mp_ensure_base_schema"
    migrations = "mp_apply_migrations"
    application_start = (
        '"${MP_COMPOSE[@]}" up -d --build --force-recreate --remove-orphans'
    )

    assert deploy_script.index(backend_build) < deploy_script.index(base_schema)
    assert deploy_script.index(base_schema) < deploy_script.index(migrations)
    assert deploy_script.index(migrations) < deploy_script.index(application_start)
    assert "deploy/migrations/*.sql" in common
    assert "basename \"$migration\"" in common
    assert "20260714_activation_email_delivery.sql" not in deploy_script
    assert "20260715_additional_passkey.sql" not in deploy_script
    windows_launcher = (root / "deploy" / "update-server.bat").read_text(
        encoding="utf-8",
    )
    assert "bash deploy/deploy.sh" in windows_launcher
    assert "deploy/migrations/202607" not in windows_launcher

    migration = "20260714_activation_email_delivery.sql"
    migration_sql = (root / "deploy" / "migrations" / migration).read_text(
        encoding="utf-8",
    )
    assert "ADD COLUMN IF NOT EXISTS delivery_pending" in migration_sql
    assert "SET value = '24'" in migration_sql

    purpose_sql = (root / "deploy" / "migrations" / "20260715_additional_passkey.sql").read_text(
        encoding="utf-8",
    )
    assert "ADD COLUMN IF NOT EXISTS purpose" in purpose_sql
    assert "additional_passkey" in purpose_sql
    assert "ALTER COLUMN purpose SET NOT NULL" in purpose_sql
