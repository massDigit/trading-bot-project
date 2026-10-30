"""Purge of every Dukascopy-derived file (operator decision of 2026-10-28, docs/DATA.md §1.3).

If Dukascopy objects to the use of its data, acquisition stops and everything derived from it is
deleted: SDK output and cache, immutable raw copies, normalized ticks, candles and quality reports.
Outside the project, the folder the JForex SDK creates is deleted only while it holds nothing but
the empty skeleton observed after our runs: anything else may belong to another JForex
installation and is left in place, reported to the operator. Nothing is deleted without `confirm`.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

SOURCE = "dukascopy"
# Created by the JForex SDK on macOS (observed 2026-10-28), outside the project.
JFOREX_APP_DIR = Path.home() / "Library" / "Application Support" / "JForex"
# Its whole content after our read-only runs (observed 2026-10-30): empty directories only.
JFOREX_SDK_SKELETON = frozenset({Path("Strategies"), Path("Strategies/files")})


@dataclass(frozen=True)
class PurgeTarget:
    path: Path
    size_bytes: int


def _size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file() and not p.is_symlink())


def is_sdk_skeleton(app_dir: Path) -> bool:
    """True if `app_dir` is a real directory holding only the empty skeleton our SDK runs create."""
    if app_dir.is_symlink() or not app_dir.is_dir():
        return False
    entries = list(app_dir.rglob("*"))
    return (
        all(e.is_dir() and not e.is_symlink() for e in entries)
        and {e.relative_to(app_dir) for e in entries} <= JFOREX_SDK_SKELETON
    )


def jforex_dir_left_in_place(jforex_app_dir: Path = JFOREX_APP_DIR) -> Path | None:
    """The JForex folder if it exists but holds something else than our skeleton (never purged)."""
    exists = jforex_app_dir.exists() or jforex_app_dir.is_symlink()
    return jforex_app_dir if exists and not is_sdk_skeleton(jforex_app_dir) else None


def purge_targets(data_dir: Path, jforex_app_dir: Path = JFOREX_APP_DIR) -> list[PurgeTarget]:
    """Existing paths that hold Dukascopy data, with their size."""
    candidates = [
        data_dir / "dukascopy-sdk",
        data_dir / "raw" / SOURCE,
        data_dir / "normalized" / "ticks" / SOURCE,
        data_dir / "bars" / SOURCE,
        *sorted((data_dir / "reports").glob(f"quality_{SOURCE}_*")),
    ]
    targets = [PurgeTarget(path, _size(path)) for path in candidates if path.exists() or path.is_symlink()]
    if is_sdk_skeleton(jforex_app_dir):
        targets.append(PurgeTarget(jforex_app_dir, 0))
    return targets


def _make_writable(function: object, path: str, _exc: BaseException) -> None:
    os.chmod(path, 0o700)
    if os.path.isdir(path):
        shutil.rmtree(path)
    else:
        os.unlink(path)


def purge(targets: list[PurgeTarget], confirm: bool) -> list[Path]:
    """Deletes the targets only if `confirm`; returns the deleted paths."""
    if not confirm:
        return []
    deleted = []
    for target in targets:
        if target.path.is_dir() and not target.path.is_symlink():
            shutil.rmtree(target.path, onexc=_make_writable)
        else:
            target.path.unlink()
        deleted.append(target.path)
    return deleted
