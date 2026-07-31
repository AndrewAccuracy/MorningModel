from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

import src.main as main_module
from better_morning.config import GlobalConfig, OutputSettings


@pytest.mark.asyncio
async def test_main_dry_run_saves_local_outputs_and_skips_history(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BETTER_MORNING_DRY_RUN", "1")

    collection_path = tmp_path / "collections" / "test.toml"
    collection_path.parent.mkdir(parents=True)
    collection_path.write_text('name = "Test"\n[[feeds]]\nurl = "https://example.com/rss"\n', encoding="utf-8")

    global_config = GlobalConfig(
        output_settings=OutputSettings(output_type="email"),
    )

    async def fake_process_collection(filepath, config):
        return (
            "Test",
            "1. **Headline** ([Source](https://example.com))\nSummary",
            [],
            [],
            {"successful": [], "failed": [], "total_feeds": 0},
            "debug report",
        )

    monkeypatch.setattr(main_module, "load_global_config", lambda: global_config)
    monkeypatch.setattr(main_module.glob, "glob", lambda pattern: [str(collection_path)])
    monkeypatch.setattr(main_module, "process_collection", fake_process_collection)
    monkeypatch.setattr(
        main_module.LLMSummarizer,
        "synthesize_one_line_take",
        AsyncMock(return_value="Dry run one-line take."),
    )

    save_digest_history = MagicMock()
    monkeypatch.setattr(
        main_module.DocumentGenerator,
        "save_digest_to_history",
        save_digest_history,
    )
    send_via_email = MagicMock()
    monkeypatch.setattr(
        main_module.DocumentGenerator,
        "send_via_email",
        send_via_email,
    )

    await main_module.main()

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    markdown_path = Path(f"dry-run-digest-{date_str}.md")
    html_path = Path(f"dry-run-digest-{date_str}.html")

    assert markdown_path.exists()
    assert html_path.exists()
    assert "Headline" in markdown_path.read_text(encoding="utf-8")
    assert "Dry run one-line take." in html_path.read_text(encoding="utf-8")
    save_digest_history.assert_not_called()
    send_via_email.assert_not_called()


def test_is_dry_run_enabled(monkeypatch):
    monkeypatch.setenv("BETTER_MORNING_DRY_RUN", "true")
    assert main_module.is_dry_run_enabled() is True

    monkeypatch.setenv("BETTER_MORNING_DRY_RUN", "0")
    assert main_module.is_dry_run_enabled() is False
