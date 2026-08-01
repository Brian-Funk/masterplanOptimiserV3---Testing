"""Resolve the exact public source repositories used by external tests."""

from __future__ import annotations

import os
from pathlib import Path


TESTING_ROOT = Path(__file__).resolve().parent

_PRODUCTS = {
    "app": {
        "environment": "MP_OPT_APP_ROOT",
        "markers": (
            Path("backend/app/main.py"),
            Path("compute/pyproject.toml"),
            Path("desktop/integrity.js"),
        ),
    },
    "server": {
        "environment": "MP_OPT_SERVER_ROOT",
        "markers": (
            Path("backend/app/main.py"),
            Path("deploy/deploy.sh"),
            Path("infra/docker-compose.prod.yml"),
        ),
    },
}


def _is_product_root(candidate: Path, markers: tuple[Path, ...]) -> bool:
    return candidate.is_dir() and all((candidate / marker).is_file() for marker in markers)


def _discovery_candidates() -> list[Path]:
    """Return bounded sibling-checkout candidates without repository-name guesses."""

    candidates: list[Path] = []
    for base in TESTING_ROOT.parents[:3]:
        candidates.append(base)
        try:
            children = [entry for entry in base.iterdir() if entry.is_dir()]
        except OSError:
            continue
        candidates.extend(children)
        for child in children:
            try:
                candidates.extend(entry for entry in child.iterdir() if entry.is_dir())
            except OSError:
                continue
    return candidates


def _resolve(product: str) -> Path:
    specification = _PRODUCTS[product]
    environment = str(specification["environment"])
    markers = tuple(specification["markers"])
    configured = os.environ.get(environment)
    if configured:
        root = Path(configured).expanduser().resolve()
        if not _is_product_root(root, markers):
            expected = ", ".join(str(marker) for marker in markers)
            raise RuntimeError(
                f"{environment} does not identify a {product} repository: {root}. "
                f"Expected markers: {expected}"
            )
        return root

    matches: list[Path] = []
    seen: set[Path] = set()
    for candidate in _discovery_candidates():
        resolved = candidate.resolve()
        if resolved not in seen and _is_product_root(resolved, markers):
            matches.append(resolved)
            seen.add(resolved)
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise RuntimeError(
            f"Could not discover the {product} repository. Set {environment} to its exact root."
        )
    formatted = ", ".join(str(match) for match in matches)
    raise RuntimeError(
        f"Multiple {product} repositories were discovered ({formatted}). "
        f"Set {environment} to the exact checkout under test."
    )


def app_root() -> Path:
    """Return the configured or uniquely discovered App source root."""

    return _resolve("app")


def server_root() -> Path:
    """Return the configured or uniquely discovered Server source root."""

    return _resolve("server")


def optional_docs_root() -> Path | None:
    """Return an explicitly configured project-site root, or disable that lane."""

    configured = os.environ.get("MP_OPT_DOCS_ROOT")
    if not configured:
        return None
    root = Path(configured).expanduser().resolve()
    markers = (Path("LICENSE"), Path("THIRD-PARTY-NOTICES.md"), Path("package.json"))
    if not _is_product_root(root, markers):
        expected = ", ".join(str(marker) for marker in markers)
        raise RuntimeError(
            f"MP_OPT_DOCS_ROOT does not identify the project-site source: {root}. "
            f"Expected markers: {expected}"
        )
    return root
