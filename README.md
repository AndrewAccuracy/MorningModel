# MorningModel

MorningModel is an AI-assisted daily email brief for international AI and finance news.

It pulls high-signal RSS sources, filters noisy items, summarizes articles with an LLM provider of your choice, and sends a Chinese morning email through iCloud SMTP.

## What You Get

- `AI Top 5`: frontier models, agents, open-source models, training/inference infrastructure, AI safety, AI policy, funding, M&A, and strategic partnerships.
- `Finance Top 5`: macro, central banks, inflation, rates, labor, GDP, equities, bonds, FX, commodities, geopolitics, and AI-related capital market news.
- `One-line Take`: one compact sentence about the main thread, market risk appetite, and what deserves follow-up.

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
BETTER_MORNING_RECIPIENT_EMAIL="yourname@icloud.com"
```

`BETTER_MORNING_SMTP_USERNAME` is both the SMTP login and the visible sender address. For iCloud, use an Apple app-specific password, not your Apple ID password.

## RSS Collections

Active collections:

- `collections/ai_news.toml`
- `collections/finance_news.toml`

Both use:

```toml
max_age = "last-digest"
```

After a successful run, timestamps are stored under `history/`, so later runs avoid repeating old articles.

## Local Run

The normal local command is:

```bash
./run.sh
```

If email credentials are missing or delivery fails, the app writes a local markdown digest named like:

```text
daily-digest-YYYY-MM-DD.md
```

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
