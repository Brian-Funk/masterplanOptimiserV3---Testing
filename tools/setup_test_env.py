#!/usr/bin/env python3
"""Create isolated external-test environments from exact source checkouts."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import venv


TESTING_ROOT = Path(__file__).resolve().parents[1]
if str(TESTING_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTING_ROOT))

from repo_roots import app_root, server_root  # noqa: E402


def _environment_python(environment: Path) -> Path:
    if sys.platform == "win32":
        return environment / "Scripts" / "python.exe"
    return environment / "bin" / "python"


def _install(environment: Path, arguments: list[str]) -> None:
    if not _environment_python(environment).is_file():
        venv.EnvBuilder(with_pip=True).create(environment)
    command = [str(_environment_python(environment)), "-m", "pip", "install", *arguments]
    subprocess.run(command, cwd=TESTING_ROOT, check=True)
    subprocess.run(
        [str(_environment_python(environment)), "-m", "pip", "check"],
        cwd=TESTING_ROOT,
        check=True,
    )


def setup_desktop() -> None:
    root = app_root()
    _install(
        TESTING_ROOT / ".venv-desktop",
        [
            "--constraint", str(root / "backend/requirements.lock.txt"),
            "--requirement", str(root / "backend/requirements.txt"),
            "--requirement", str(root / "compute/requirements-dev.txt"),
            "--requirement", str(TESTING_ROOT / "requirements-desktop.txt"),
        ],
    )


def setup_server() -> None:
    root = server_root()
    _install(
        TESTING_ROOT / ".venv-server",
        [
            "--requirement", str(root / "backend/requirements-test.txt"),
            "--requirement", str(TESTING_ROOT / "requirements-server.txt"),
        ],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("product", choices=("desktop", "server", "all"))
    arguments = parser.parse_args()
    if arguments.product in {"desktop", "all"}:
        setup_desktop()
    if arguments.product in {"server", "all"}:
        setup_server()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
