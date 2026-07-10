"""Install hooks/pre-commit into .git/hooks/pre-commit.

Phase 1 installs this on the macOS dev box too (open-questions #1) —
agents committing GPX here deserve the same backstop the Route Manager
will install for the Windows BFU in Phase 2.

Usage: python3 pipeline/install_hooks.py
"""

import shutil
import stat
import sys
from pathlib import Path


def repo_root():
    # This file lives at <repo>/pipeline/install_hooks.py, so the repo
    # root is two levels up. Deriving it from __file__ (instead of
    # shelling out to `git rev-parse`) means no dependency on a `git`
    # CLI on PATH — the Windows maintainer uses GitHub Desktop, which
    # bundles git but does not expose it, so `git ...` raises WinError 2.
    root = Path(__file__).resolve().parent.parent
    if not (root / ".git").exists():
        raise FileNotFoundError(
            f"not a git repo (no .git found at {root}) — run this from "
            "inside the cloned cyklocesta repository"
        )
    return root


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
