# AI + Finance International Morning Brief

This repository has been configured as a daily AI and finance email digest.

## What Changed

- Added `collections/ai_news.toml` for international AI news.
- Added `collections/finance_news.toml` for global macro and market news.
- Moved the original sample collections to `.toml.back` so only AI and Finance run by default.
- Updated `config.toml` for Chinese output, OpenAI models, iCloud SMTP, full-article extraction, LLM filtering, and digest prompts.
- Updated `.github/workflows/daily_digest.yml` to run daily at 23:00 UTC, which is 07:00 Beijing time.
- Updated the email subject to `[Morning Brief] AI + Finance Daily Digest | YYYY-MM-DD`.
- Updated markdown generation so the digest contains:
  - `AI Top 5`
  - `Finance Top 5`
  - `One-line Take`

## Local Run

Install dependencies:

```bash
pip install uv
uv sync
```

Create your local secrets file:

```bash
cp .env.local.example .env.local
```

Then edit `.env.local` and fill in:

- One of `BETTER_MORNING_OPENAI_API_KEY`, `BETTER_MORNING_DEEPSEEK_API_KEY`, or `BETTER_MORNING_GEMINI_API_KEY`
- `BETTER_MORNING_LLM_PROVIDER`, only if more than one provider key is filled
- `BETTER_MORNING_SMTP_USERNAME`
- `BETTER_MORNING_SMTP_PASSWORD`
- `BETTER_MORNING_RECIPIENT_EMAIL`

`.env.local` is ignored by git and should never be committed.

Run locally:

```bash
./run.sh
```

If email settings are missing, the script saves a local markdown file named like `daily-digest-YYYY-MM-DD.md`.

## GitHub Actions

The workflow supports manual runs through `workflow_dispatch` and scheduled runs at 23:00 UTC daily.

Add the relevant repository secrets:

- One of `BETTER_MORNING_OPENAI_API_KEY`, `BETTER_MORNING_DEEPSEEK_API_KEY`, or `BETTER_MORNING_GEMINI_API_KEY`
- `BETTER_MORNING_LLM_PROVIDER`, only if more than one provider key is filled
- `BETTER_MORNING_SMTP_USERNAME`
- `BETTER_MORNING_SMTP_PASSWORD`
- `BETTER_MORNING_RECIPIENT_EMAIL`

For iCloud Mail, `BETTER_MORNING_SMTP_USERNAME` is also the sender address shown in the email. Use an Apple app-specific password for `BETTER_MORNING_SMTP_PASSWORD`.

Default model profiles use LiteLLM names:

- OpenAI: `openai/gpt-4o`, `openai/gpt-4o-mini`
- DeepSeek: `deepseek/deepseek-reasoner`, `deepseek/deepseek-chat`
- Gemini: `gemini/gemini-2.5-pro`, `gemini/gemini-2.5-flash`

## Iteration Notes

Start with the current 6-8 sources per category. After several real runs, remove feeds that frequently fail or produce low-signal stories, then tighten or relax the collection `filter_query` values based on actual output quality.
