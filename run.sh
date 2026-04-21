#!/bin/sh
set -eu

cd "$(dirname "$0")"

if [ "${1:-}" = "--scheduled" ]; then
  INTERVAL_DAYS="${BETTER_MORNING_RUN_INTERVAL_DAYS:-5}"
  if [ ! -x ".venv/bin/python" ]; then
    echo "Missing .venv. Run: python3 -m venv .venv && .venv/bin/python -m pip install uv && .venv/bin/uv sync" >&2
    exit 1
  fi
  .venv/bin/python scripts/run_if_due.py --root "$(pwd)" --interval-days "$INTERVAL_DAYS" -- ./run.sh --force
  exit $?
fi

if [ "${1:-}" = "--force" ]; then
  shift
fi

if [ "${BETTER_MORNING_CLEAR_LOGS_ON_RUN:-1}" = "1" ]; then
  : > run.log
  : > run.err.log
fi

ENV_FILE=".env.local"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE. Create it from .env.local.example and fill in your local secrets." >&2
  exit 1
fi

set -a
. "./$ENV_FILE"
set +a

export PYTHONPATH="src:${PYTHONPATH:-}"

if [ ! -x ".venv/bin/python" ]; then
  echo "Missing .venv. Run: python3 -m venv .venv && .venv/bin/python -m pip install uv && .venv/bin/uv sync" >&2
  exit 1
fi

.venv/bin/python scripts/cleanup_old_data.py --days 90
.venv/bin/python run_local.py
