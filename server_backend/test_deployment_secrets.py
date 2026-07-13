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
        "secrets/root_bootstrap_token"
        in deploy_script
    )


def test_deploy_preserves_an_empty_bootstrap_secret():
    """An existing empty secret must continue to mean bootstrap is disabled."""
    deploy_script = (_server_root() / "deploy" / "deploy.sh").read_text(
        encoding="utf-8",
    )

    assert 'if [ ! -e "secrets/root_bootstrap_token" ]; then' in deploy_script
    assert 'if [ ! -s "secrets/root_bootstrap_token" ]; then' not in deploy_script
