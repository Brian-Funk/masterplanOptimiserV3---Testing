#!/usr/bin/env python3
"""Run the Phase F synthetic qualification and emit an exact-head receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_PLAN = Path(__file__).with_name("phase_f_exact_stack_plan.json")


def _run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)


def _git(root: Path, *arguments: str) -> str:
    result = _run(["git", *arguments], root)
    if result.returncode:
        raise RuntimeError(f"git {' '.join(arguments)} failed for {root}: {result.stderr.strip()}")
    return result.stdout.strip()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repository_roots(plan: dict[str, Any], eyp_root: Path) -> dict[str, Path]:
    roots: dict[str, Path] = {}
    for name, definition in plan["repositories"].items():
        configured = os.environ.get(definition["environment"])
        root = Path(configured) if configured else eyp_root / definition["default_relative"]
        root = root.expanduser().resolve()
        if not (root / ".git").exists():
            raise RuntimeError(f"{name} repository is unavailable at {root}")
        roots[name] = root
    return roots


def _command(value: list[str]) -> list[str]:
    command = list(value)
    if command[0] == "python":
        command[0] = sys.executable
    elif command[0] == "npm" and os.name == "nt":
        command[0] = shutil.which("npm.cmd") or "npm.cmd"
    return command


def execute(
    plan_path: Path,
    output: Path,
    *,
    eyp_root: Path,
    allow_dirty: bool = False,
    lane_ids: set[str] | None = None,
) -> dict[str, Any]:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if plan.get("format") != "masterplan-phase-f-exact-stack-plan-v1":
        raise ValueError("Unsupported Phase F plan format")
    roots = _repository_roots(plan, eyp_root)
    repositories: dict[str, Any] = {}
    invalid_dirty: list[str] = []
    for name, root in roots.items():
        dirty = _git(root, "status", "--porcelain").splitlines()
        repositories[name] = {
            "path": str(root),
            "head_sha": _git(root, "rev-parse", "HEAD"),
            "tree_sha": _git(root, "rev-parse", "HEAD^{tree}"),
            "origin": _git(root, "remote", "get-url", "origin"),
            "dirty": dirty,
        }
        if dirty and not allow_dirty:
            invalid_dirty.append(name)
    if invalid_dirty:
        raise RuntimeError("Exact run requires clean worktrees: " + ", ".join(invalid_dirty))

    lane_results: list[dict[str, Any]] = []
    for lane in plan["lanes"]:
        if lane_ids is not None and lane["id"] not in lane_ids:
            continue
        root = roots[lane["repository"]]
        cwd = (root / lane["cwd"]).resolve()
        command = _command(lane["command"])
        started = datetime.now(timezone.utc)
        result = _run(command, cwd)
        lane_results.append({
            "id": lane["id"],
            "repository": lane["repository"],
            "covers": lane["covers"],
            "command": command,
            "started_at": started.isoformat(),
            "duration_seconds": round((datetime.now(timezone.utc) - started).total_seconds(), 3),
            "returncode": result.returncode,
            "stdout_sha256": hashlib.sha256(result.stdout.encode("utf-8")).hexdigest(),
            "stderr_sha256": hashlib.sha256(result.stderr.encode("utf-8")).hexdigest(),
            "stdout_tail": result.stdout[-4000:],
            "stderr_tail": result.stderr[-4000:],
            "passed": result.returncode == 0,
        })

    receipt = {
        "format": "masterplan-phase-f-exact-stack-receipt-v1",
        "roadmap_version": plan["roadmap_version"],
        "requirements": plan["requirements"],
        "plan_sha256": _sha256(plan_path),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "synthetic_only": True,
        "repositories": repositories,
        "lanes": lane_results,
        "exclusions": plan["exclusions"],
        "passed": bool(lane_results) and all(item["passed"] for item in lane_results),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=output.parent, delete=False, prefix=f".{output.name}.",
    ) as handle:
        json.dump(receipt, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, output)
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--eyp-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--lane", action="append", dest="lanes")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        receipt = execute(
            args.plan.resolve(), args.output.resolve(), eyp_root=args.eyp_root.resolve(),
            allow_dirty=args.allow_dirty, lane_ids=set(args.lanes) if args.lanes else None,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Phase F qualification failed: {exc}", file=sys.stderr)
        return 1
    print(f"Phase F receipt: {args.output.resolve()}")
    print(f"Result: {'passed' if receipt['passed'] else 'failed'}")
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
