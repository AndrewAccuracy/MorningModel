# MorningModel

MorningModel is an AI-assisted daily email brief for international AI and finance news.

It pulls high-signal RSS sources, filters noisy items, summarizes articles with an LLM provider of your choice, and sends a Chinese morning email through iCloud SMTP.
Sources include official feeds, major media, research feeds, Medium tags, and selected Substack/newsletter feeds.

## What You Get

- `AI Top 10`: frontier models, agents, open-source models, training/inference infrastructure, AI safety, AI policy, funding, M&A, and strategic partnerships.
- `AI Research & Safety Top 10`: AI research, arXiv papers, AI safety, alignment, evaluations, red teaming, interpretability, and selected journal/community research.
- `Finance Top 10`: FT/WSJ-style macro and market direction, central banks, inflation, rates, labor, GDP, equities, bonds, FX, commodities, geopolitics, and AI-related capital market news.
- `One-line Take`: one compact sentence about the main thread, market risk appetite, and what deserves follow-up.

Each selected item ends with `入选优势`, a short editor-style note explaining why that item deserves a slot in the final list.

## Quick Start

Install dependencies:

```bash
pip install uv
uv sync
```

Create your local secrets file:

```bash
cp .env.local.example .env.local
```

Edit `.env.local`, then run:

```bash
./run.sh
```

`.env.local` is ignored by git. Do not commit API keys, iCloud app-specific passwords, or recipient addresses.

## LLM Provider Setup

MorningModel uses LiteLLM model names and can auto-select OpenAI, DeepSeek, or Gemini.

Fill in one provider key and leave the others empty:

```bash
BETTER_MORNING_OPENAI_API_KEY=""
BETTER_MORNING_DEEPSEEK_API_KEY=""
BETTER_MORNING_GEMINI_API_KEY=""
BETTER_MORNING_LLM_PROVIDER="auto"
```

If more than one provider key is filled, set:

```bash
BETTER_MORNING_LLM_PROVIDER="openai"
```

Supported values are `auto`, `openai`, `deepseek`, and `gemini`.

Default model profiles:

| Provider | Reasoner model | Light model | Filter model |
| --- | --- | --- | --- |
| OpenAI | `openai/gpt-4o` | `openai/gpt-4o-mini` | `openai/gpt-4o` |
| DeepSeek | `deepseek/deepseek-reasoner` | `deepseek/deepseek-chat` | `deepseek/deepseek-chat` |
| Gemini | `gemini/gemini-2.5-pro` | `gemini/gemini-2.5-flash` | `gemini/gemini-2.5-flash` |

Advanced users can override the defaults:

```bash
BETTER_MORNING_REASONER_MODEL=""
BETTER_MORNING_LIGHT_MODEL=""
BETTER_MORNING_FILTER_MODEL=""
```

Leave these empty unless you intentionally want custom LiteLLM model names.

## Email Setup

The default email transport is iCloud Mail:

```toml
[output_settings]
output_type = "email"
smtp_server = "smtp.mail.me.com"
smtp_port = 587
```

Set these in `.env.local`:

```bash
BETTER_MORNING_SMTP_USERNAME="yourname@icloud.com"
BETTER_MORNING_SMTP_PASSWORD="your-icloud-app-specific-password"
BETTER_MORNING_RECIPIENT_EMAIL="yourname@icloud.com,another@example.com"
```

`BETTER_MORNING_SMTP_USERNAME` is both the SMTP login and the visible sender address. For iCloud, use an Apple app-specific password, not your Apple ID password.
Use a single address or multiple recipients separated by commas, semicolons, or new lines.

## RSS Collections

Active collections:

- `collections/ai_news.toml`
- `collections/ai_research_safety.toml`
- `collections/finance_news.toml`

These collections use:

```toml
max_age = "last-digest"
```

After a successful run, timestamps are stored under `history/`, so later runs avoid repeating old articles.

To add or remove sites, edit the relevant collection file and add another `[[feeds]]` block:

```toml
[[feeds]]
url = "https://example.com/rss.xml"
name = "Example Source"
max_articles = 20
```

Use `collections/ai_news.toml` for AI industry/news sources, `collections/ai_research_safety.toml` for AI research and safety sources, and `collections/finance_news.toml` for finance and market sources.

The source mix combines official feeds, research feeds, mainstream media, and selected open-platform analysis. Noisy sources can be narrowed with per-feed `filter_query` rules.

## Security Guardrails

RSS items, web pages, PDFs, and previous digest history are treated as untrusted input. The pipeline normalizes source text, wraps untrusted content before LLM calls, filters suspicious items, and checks model outputs for signs of prompt-injection influence. These guardrails reduce risk, but curated sources and careful secret handling are still required.

## Local Run

The normal local command is:

```bash
./run.sh
```

Each run clears the previous `run.log` / `run.err.log` files before writing new output, then prunes local data older than 90 days through `scripts/cleanup_old_data.py`. Article history is already kept short by the app's normal history retention, but this cleanup also trims old JSON history records and removes stale generated digest/debug files.

If you want to keep old logs for debugging, run with:

```bash
BETTER_MORNING_CLEAR_LOGS_ON_RUN=0 ./run.sh
```

If email credentials are missing or delivery fails, the app writes a local markdown digest named like:

```text
daily-digest-YYYY-MM-DD.md
```

For local automation, use:

```bash
./run.sh --scheduled
```

`run.sh --scheduled` is a lightweight guarded mode. It checks `history/scheduler_state.json` and only runs the full digest when the configured interval is due. By default the interval is 5 days; override it with:

```bash
BETTER_MORNING_RUN_INTERVAL_DAYS=1 ./run.sh --scheduled
```

The scheduler state file is overwritten on each scheduled attempt rather than appended, so it stays small. If the Mac is off exactly when the 5-day interval becomes due, the next scheduled check after reboot/login will see that `last_success_at + interval` has passed and will run the digest.

On macOS, avoid placing the automated checkout under privacy-protected folders such as `Desktop` or `Documents` unless you explicitly grant the background process access in System Settings. LaunchAgents may fail with `Operation not permitted` when they try to execute or read scripts in those folders. A path such as `~/Code/better-morning` or `~/.local/share/better-morning` is usually easier for local automation.

## macOS Local Schedule

For local automation on macOS, use a LaunchAgent that periodically runs:

```bash
./run.sh --scheduled
```

The recommended pattern is a frequent lightweight check, not a long one-shot timer:

`StartInterval = 43200` asks macOS to check roughly every 12 hours, and `RunAtLoad = true` asks it to check after login/load. The expensive digest still runs only when `run.sh --scheduled` determines that the configured digest interval is due.

To change the digest cadence, prefer setting `BETTER_MORNING_RUN_INTERVAL_DAYS` for `run.sh --scheduled` instead of making the LaunchAgent interval very long.

## GitHub Actions

`.github/workflows/daily_digest.yml` supports:

- Manual runs through `workflow_dispatch`
- Daily scheduled runs at 23:00 UTC, equal to 07:00 Beijing time

Recommended GitHub Actions secrets:

- One of:
  - `BETTER_MORNING_OPENAI_API_KEY`
  - `BETTER_MORNING_DEEPSEEK_API_KEY`
  - `BETTER_MORNING_GEMINI_API_KEY`
- Optional when more than one provider key is configured:
  - `BETTER_MORNING_LLM_PROVIDER`
- Required for email:
  - `BETTER_MORNING_SMTP_USERNAME`
  - `BETTER_MORNING_SMTP_PASSWORD`
  - `BETTER_MORNING_RECIPIENT_EMAIL`

## Project Notes

- Global settings live in `config.toml`.
- Source lists live in `docs/rss_sources.md`.
- Run and deployment checks live in `docs/test_checklist.md`.
- Prompt-injection and untrusted-content handling lives in `src/better_morning/prompt_security.py`.
- The app relies on `litellm`, `feedparser`, `trafilatura`, and Playwright for its news pipeline.

## Attribution

MorningModel is adapted from [`00sapo/better-morning`](https://github.com/00sapo/better-morning). The original project provides the configurable RSS collection system, article extraction pipeline, LLM summarization flow, history handling, email output, and GitHub Actions structure.

## License

This repository is based on GPL v3 licensed code. The GPL v3 license text is preserved in `LICENSE`.
