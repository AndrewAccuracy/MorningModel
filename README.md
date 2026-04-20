# MorningModel

MorningModel is an AI-assisted daily email brief for international AI and finance news.

It pulls high-signal RSS sources, filters noisy items, summarizes articles with an LLM provider of your choice, and sends a Chinese morning email through iCloud SMTP.

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

## Local Run

The normal local command is:

```bash
./run.sh
```

Each run first prunes local data older than 90 days through `scripts/cleanup_old_data.py`. Article history is already kept short by the app's normal history retention, but this cleanup also trims old JSON history records, removes stale generated digest/debug files, and truncates `run.log` / `run.err.log` if either grows beyond 5 MB.

If email credentials are missing or delivery fails, the app writes a local markdown digest named like:

```text
daily-digest-YYYY-MM-DD.md
```

## macOS Daily Schedule

For the lightest local automation, use a macOS LaunchAgent. This does not keep Python running in the background; macOS wakes it on a fixed interval, runs `run.sh`, then exits.

The current LaunchAgent is:

```text
~/Library/LaunchAgents/com.hy.better-morning.plist
```

It currently runs this script once every 5 days:

```text
/Users/hy/Desktop/Good_morning/better-morning/run.sh
```

Logs are written to:

```text
/Users/hy/Desktop/Good_morning/better-morning/run.log
/Users/hy/Desktop/Good_morning/better-morning/run.err.log
```

Useful commands:

```bash
# Check status
launchctl print gui/$(id -u)/com.hy.better-morning

# Run once immediately for testing
launchctl kickstart -k gui/$(id -u)/com.hy.better-morning

# Disable/unload the schedule
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.hy.better-morning.plist

# Reload after editing the plist
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.hy.better-morning.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.hy.better-morning.plist
```

To change the cadence, edit the `StartInterval` value in the plist, then reload it with the commands above. The current value is `432000` seconds, equal to 5 days.

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
- The app relies on `litellm`, `feedparser`, `trafilatura`, and Playwright for its news pipeline.

## Attribution

MorningModel is adapted from [`00sapo/better-morning`](https://github.com/00sapo/better-morning). The original project provides the configurable RSS collection system, article extraction pipeline, LLM summarization flow, history handling, email output, and GitHub Actions structure.

## License

This repository is based on GPL v3 licensed code. The GPL v3 license text is preserved in `LICENSE`.
