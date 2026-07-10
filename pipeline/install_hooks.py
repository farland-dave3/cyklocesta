"""Install hooks/pre-commit into .git/hooks/pre-commit.

Phase 1 installs this on the macOS dev box too (open-questions #1) —
agents committing GPX here deserve the same backstop the Route Manager
will install for the Windows BFU in Phase 2.

Usage: python3 pipeline/install_hooks.py
"""

import shutil
import stat
import subprocess
import sys
from pathlib import Path


def repo_root():
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(out.stdout.strip())


def install():
    root = repo_root()
    src = root / "hooks" / "pre-commit"
    dest = root / ".git" / "hooks" / "pre-commit"

    if not src.exists():
        raise FileNotFoundError(f"hook source missing: {src}")

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    mode = dest.stat().st_mode
    dest.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"Installed pre-commit hook: {dest}")
    return dest


if __name__ == "__main__":
    try:
        install()
    except Exception as exc:  # noqa: BLE001 - CLI top-level
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
