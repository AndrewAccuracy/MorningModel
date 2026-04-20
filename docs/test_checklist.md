# Test Checklist

## Local Test

- Run `uv sync`.
- Copy `.env.local.example` to `.env.local` and fill in local secrets.
- Confirm the model variables in `.env.local` match your provider.
- Run `./run.sh`.
- Confirm the run either sends email or creates `daily-digest-YYYY-MM-DD.md`.
- Confirm only `AI Top 10`, `AI Research & Safety Top 10`, `Finance Top 10`, and diagnostics are present.

## Secrets Check

- Confirm exactly one provider API key is set, or set `BETTER_MORNING_LLM_PROVIDER` explicitly.
- Confirm optional model override variables are empty unless intentionally overriding defaults.
- Confirm `BETTER_MORNING_SMTP_USERNAME` is set to the sender iCloud email address.
- Confirm `BETTER_MORNING_SMTP_PASSWORD` is an Apple app-specific password.
- Confirm `BETTER_MORNING_RECIPIENT_EMAIL` is set.

## Cron Check

- Confirm `.github/workflows/daily_digest.yml` has `workflow_dispatch`.
- Confirm cron is daily at 23:00 UTC.
- Confirm 23:00 UTC equals 07:00 Beijing time the next day.

## Email Verification

- Confirm the subject is `[Morning Brief] AI + Finance Daily Digest | YYYY-MM-DD`.
- Confirm the body is Chinese.
- Confirm AI, AI Research & Safety, and Finance sections render cleanly in the email client.
- Confirm each item includes original title, source, summary, and importance or market impact.

## Duplicate News Check

- Run once and verify `history/` is created.
- Run a second time after a successful output.
- Confirm `max_age = "last-digest"` reduces repeated stories.
- Check whether similar titles still recur across feeds; if so, tighten the collection filter or remove duplicate-heavy sources.
