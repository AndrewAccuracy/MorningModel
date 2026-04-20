from datetime import datetime, timezone

from better_morning.config import GlobalConfig, OutputSettings
from better_morning.document_generator import DocumentGenerator


def test_save_and_load_digest_history(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    global_config = GlobalConfig(
        output_settings=OutputSettings(),
        context_digest_size=2,
    )
    generator = DocumentGenerator(global_config.output_settings, global_config)

    collection_summaries = {"News": "Summary content"}
    today = datetime(2025, 1, 5, tzinfo=timezone.utc)

    generator.save_digest_to_history(collection_summaries, today)

    previous = generator.load_previous_digests()
    assert len(previous) == 1
    assert "Summary content" in previous[0]["content"]

    context = generator.get_context_for_llm()
    assert "Digest from 2025-01-05" in context


def test_parse_multiple_recipient_emails():
    global_config = GlobalConfig(output_settings=OutputSettings())
    generator = DocumentGenerator(global_config.output_settings, global_config)

    recipients = generator._parse_recipient_emails(
        "one@example.com, two@example.com;three@example.com\nfour@example.com"
    )

    assert recipients == [
        "one@example.com",
        "two@example.com",
        "three@example.com",
        "four@example.com",
    ]


def test_section_title_distinguishes_ai_research_safety():
    global_config = GlobalConfig(output_settings=OutputSettings())
    generator = DocumentGenerator(global_config.output_settings, global_config)

    assert (
        generator._section_title("AI Research & Safety Top 10")
        == "AI Research & Safety Top 10"
    )
    assert generator._section_title("AI Top 10") == "AI Top 10"
