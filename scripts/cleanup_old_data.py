#!/usr/bin/env python3
"""Prune old local data before a scheduled digest run."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def prune_json_list(path: Path, cutoff: datetime) -> int:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0

    if not isinstance(data, list):
        return 0

    kept = []
    removed = 0
    for item in data:
        if not isinstance(item, dict):
            kept.append(item)
            continue

        item_date = parse_datetime(item.get("published_date") or item.get("date"))
        if item_date is None or item_date >= cutoff:
            kept.append(item)
        else:
            removed += 1

    if removed:
        path.write_text(
            json.dumps(kept, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return removed


def delete_old_files(root: Path, cutoff: datetime) -> int:
    patterns = [
        "daily-digest-*.md",
        "debug/**/*",
    ]
    removed = 0
    cutoff_ts = cutoff.timestamp()
    for pattern in patterns:
        for path in root.glob(pattern):
            if not path.is_file():
                continue
            try:
                if path.stat().st_mtime < cutoff_ts:
                    path.unlink()
                    removed += 1
            except OSError:
                continue
    return removed


def truncate_large_logs(root: Path, max_bytes: int) -> int:
    truncated = 0
    for path in [root / "run.log", root / "run.err.log"]:
        try:
            if path.exists() and path.stat().st_size > max_bytes:
                path.write_text("", encoding="utf-8")
                truncated += 1
        except OSError:
            continue
    return truncated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()

    root = args.root.resolve()
    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)

    removed_records = 0
    history_dir = root / "history"
    if history_dir.exists():
        for path in history_dir.glob("*.json"):
            removed_records += prune_json_list(path, cutoff)

    removed_files = delete_old_files(root, cutoff)
    truncated_logs = truncate_large_logs(root, max_bytes=5 * 1024 * 1024)

    print(
        f"Cleanup complete: removed {removed_records} history records and "
        f"{removed_files} old files older than {args.days} days; "
        f"truncated {truncated_logs} oversized log files."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
