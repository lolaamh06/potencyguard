"""Run all project checks: ruff, format, pytest, the Phase 4 and 5 checks and the dashboard."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD = REPO_ROOT / "dashboard"
TAIL_LINES = 25


def _run(name: str, command: list[str], cwd: Path) -> bool:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    ok = result.returncode == 0
    print(f"{'PASS' if ok else 'FAIL'}: {name}")
    if not ok:
        output = (result.stdout + result.stderr).strip().splitlines()
        print("\n".join(output[-TAIL_LINES:]))
    return ok


def main() -> int:
    py = sys.executable
    checks: list[tuple[str, list[str], Path]] = [
        ("ruff check", [py, "-m", "ruff", "check", "."], REPO_ROOT),
        ("ruff format --check", [py, "-m", "ruff", "format", "--check", "."], REPO_ROOT),
        ("pytest", [py, "-m", "pytest", "-q"], REPO_ROOT),
        ("phase 4 chain check", [py, "scripts/check_phase4.py"], REPO_ROOT),
        ("phase 5 planner check", [py, "scripts/check_phase5.py"], REPO_ROOT),
    ]
    npm = shutil.which("npm")
    if (DASHBOARD / "package.json").exists() and (DASHBOARD / "node_modules").exists():
        if npm is None:
            print("FAIL: npm not found on PATH")
            return 1
        checks.append(("dashboard build", [npm, "run", "build"], DASHBOARD))
        checks.append(("dashboard test", [npm, "test"], DASHBOARD))
    else:
        print("SKIP: dashboard checks (no package.json or node_modules yet)")

    results = [_run(name, cmd, cwd) for name, cmd, cwd in checks]
    failed = results.count(False)
    print(f"Summary: {len(results) - failed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
