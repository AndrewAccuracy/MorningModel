import json
from datetime import datetime, timedelta, timezone

from scripts.run_if_due import is_due, load_state, parse_datetime, save_state


def test_parse_datetime_handles_iso_utc():
    parsed = parse_datetime("2026-04-21T01:02:03+00:00")
    assert parsed == datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc)


def test_is_due_without_success_timestamp():
    due, reason = is_due({}, datetime(2026, 4, 21, tzinfo=timezone.utc), timedelta(days=5))
    assert due is True
    assert "no previous" in reason


def test_is_due_after_interval_elapsed():
    now = datetime(2026, 4, 21, tzinfo=timezone.utc)
    state = {"last_success_at": "2026-04-15T00:00:00+00:00"}
    due, reason = is_due(state, now, timedelta(days=5))
    assert due is True
    assert "due since" in reason


def test_is_due_exactly_at_interval_boundary():
    now = datetime(2026, 4, 20, tzinfo=timezone.utc)
    state = {"last_success_at": "2026-04-15T00:00:00+00:00"}
    due, reason = is_due(state, now, timedelta(days=5))
    assert due is True
    assert "due since" in reason


def test_is_not_due_before_interval_elapsed():
    now = datetime(2026, 4, 21, tzinfo=timezone.utc)
    state = {"last_success_at": "2026-04-18T00:00:00+00:00"}
    due, reason = is_due(state, now, timedelta(days=5))
    assert due is False
    assert "next due" in reason


def test_state_round_trip(tmp_path):
    path = tmp_path / "history" / "scheduler_state.json"
    state = {"last_success_at": "2026-04-21T00:00:00+00:00"}
    save_state(path, state)
    assert json.loads(path.read_text(encoding="utf-8")) == state
    assert load_state(path) == state
