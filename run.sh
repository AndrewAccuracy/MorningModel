#!/bin/sh
set -eu

cd "$(dirname "$0")"

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

.venv/bin/python run_local.py
