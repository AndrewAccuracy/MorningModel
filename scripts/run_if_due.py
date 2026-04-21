#!/usr/bin/env python3
"""Run a command only when the scheduled digest interval is due.

This wrapper makes local scheduling resilient to sleep, shutdown, and missed
LaunchAgent intervals. launchd can wake this script frequently; the script keeps
its own last-success timestamp and runs the expensive digest only when due.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def load_state(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def is_due(
    state: dict[str, Any],
    now: datetime,
    interval: timedelta,
    force: bool = False,
) -> tuple[bool, str]:
    if force:
        return True, "forced run requested"

    last_success = parse_datetime(state.get("last_success_at"))
    if last_success is None:
        return True, "no previous successful scheduled run"

    next_due = last_success + interval
    if now >= next_due:
        return True, f"due since {next_due.isoformat()}"

    return False, f"next due at {next_due.isoformat()}"


def acquire_lock(lock_path: Path, now: datetime, stale_after: timedelta) -> bool:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            stat = lock_path.stat()
        except OSError:
            return False
        lock_age = now - datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        if lock_age <= stale_after:
            return False
        try:
            lock_path.unlink()
        except OSError:
            return False
        return acquire_lock(lock_path, now, stale_after)

    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(now.isoformat())
    return True


def release_lock(lock_path: Path) -> None:
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--state-file", type=Path)
    parser.add_argument("--lock-file", type=Path)
    parser.add_argument("--interval-days", type=float, default=5.0)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    root = args.root.resolve()
    state_file = args.state_file or root / "history" / "scheduler_state.json"
    lock_file = args.lock_file or root / "history" / "scheduler.lock"
    command = args.command or ["./run.sh"]
    if command and command[0] == "--":
        command = command[1:]

    now = utc_now()
    interval = timedelta(days=args.interval_days)
    state = load_state(state_file)
    due, reason = is_due(state, now, interval, force=args.force)

    if not due:
        print(f"Scheduled digest skipped: {reason}")
        return 0

    if not acquire_lock(lock_file, now, stale_after=timedelta(hours=8)):
        print("Scheduled digest skipped: another run appears to be active.")
        return 0

    state["last_attempt_at"] = now.isoformat()
    state["last_due_reason"] = reason
    save_state(state_file, state)

    try:
        print(f"Scheduled digest running: {reason}")
        result = subprocess.run(command, cwd=root, check=False)
        finished_at = utc_now()
        state = load_state(state_file)
        state["last_finished_at"] = finished_at.isoformat()
        state["last_exit_code"] = result.returncode
        if result.returncode == 0:
            state["last_success_at"] = finished_at.isoformat()
            state["last_error"] = None
        else:
            state["last_error"] = f"command exited with {result.returncode}"
        save_state(state_file, state)
        return result.returncode
    finally:
        release_lock(lock_file)


if __name__ == "__main__":
    raise SystemExit(main())
