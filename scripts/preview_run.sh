#!/bin/sh
# Generate today's digest locally (no email) and open an HTML preview in the browser.
set -eu

cd "$(dirname "$0")/.."

ENV_FILE=".env.local"
if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE. Copy from .env.local.example and fill in API keys." >&2
  exit 1
fi

set -a
. "./$ENV_FILE"
set +a

# Preview only: do not send mail even if SMTP is configured.
unset BETTER_MORNING_SMTP_USERNAME
unset BETTER_MORNING_SMTP_PASSWORD
unset BETTER_MORNING_RECIPIENT_EMAIL

export PYTHONPATH="src:${PYTHONPATH:-}"
export BETTER_MORNING_CLEAR_LOGS_ON_RUN=0

if [ ! -x ".venv/bin/python" ]; then
  echo "Missing .venv. Run: python3 -m venv .venv && .venv/bin/python -m pip install uv && .venv/bin/uv sync" >&2
  exit 1
fi

.venv/bin/python scripts/cleanup_old_data.py --days 90
.venv/bin/python run_local.py

TODAY=$(date +%Y-%m-%d)
MD="daily-digest-${TODAY}.md"
HTML="daily-digest-${TODAY}.html"

if [ ! -f "$MD" ]; then
  echo "No digest file at $MD — run may have failed. Check run-preview.log" >&2
  exit 1
fi

.venv/bin/python - <<'PY'
import pathlib
import markdown2

today = __import__("datetime").date.today().isoformat()
md_path = pathlib.Path(f"daily-digest-{today}.md")
html_path = pathlib.Path(f"daily-digest-{today}.html")
body = markdown2.markdown(md_path.read_text(encoding="utf-8"))
html_path.write_text(
    f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Morning Brief Preview — {today}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
           line-height: 1.5; max-width: 720px; margin: 2rem auto; padding: 0 1rem;
           color: #1a1a1a; }}
    h1, h2, h3 {{ line-height: 1.25; }}
    a {{ color: #0066cc; }}
    blockquote {{ border-left: 3px solid #ddd; margin-left: 0; padding-left: 1rem; color: #444; }}
    hr {{ border: none; border-top: 1px solid #e5e5e5; margin: 1.5rem 0; }}
  </style>
</head>
<body>
{body}
</body>
</html>
""",
    encoding="utf-8",
)
print(f"Wrote {html_path}")
PY

echo "Opening $HTML ..."
if command -v open >/dev/null 2>&1; then
  open "$HTML"
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$HTML"
else
  echo "file://$(pwd)/$HTML"
fi
