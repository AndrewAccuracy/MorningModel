from datetime import datetime, timezone
from html import unescape
import smtplib
from urllib.parse import parse_qs, urlparse

from better_morning.config import GlobalConfig, OutputSettings
from better_morning.document_generator import DocumentGenerator
from better_morning.rss_fetcher import Article


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


def test_send_via_email_returns_false_on_smtp_error(monkeypatch):
    monkeypatch.setenv("BETTER_MORNING_SMTP_USERNAME", "sender@example.com")
    monkeypatch.setenv("BETTER_MORNING_SMTP_PASSWORD", "password")

    global_config = GlobalConfig(
        output_settings=OutputSettings(
            output_type="email",
            smtp_server="smtp.example.com",
            smtp_port=587,
        )
    )
    generator = DocumentGenerator(global_config.output_settings, global_config)

    def fail_smtp(*args, **kwargs):
        raise smtplib.SMTPServerDisconnected("timed out")

    monkeypatch.setattr(smtplib, "SMTP", fail_smtp)

    assert (
        generator.send_via_email(
            "Subject",
            "Body",
            "recipient@example.com",
        )
        is False
    )


def test_section_title_distinguishes_ai_research_safety():
    global_config = GlobalConfig(output_settings=OutputSettings())
    generator = DocumentGenerator(global_config.output_settings, global_config)

    assert (
        generator._section_title("AI Research & Safety Top 10")
        == "AI Research & Safety Top 10"
    )
    assert generator._section_title("AI Top 10") == "AI Top 10"


def test_email_html_includes_mailto_feedback_actions(monkeypatch):
    monkeypatch.setenv("BETTER_MORNING_FEEDBACK_EMAIL", "feedback@example.com")
    global_config = GlobalConfig(output_settings=OutputSettings())
    generator = DocumentGenerator(global_config.output_settings, global_config)
    article = Article(
        id="a1",
        title="OpenAI launches new agent platform",
        link="https://techcrunch.com/openai-agent",
        source_url="https://techcrunch.com/category/artificial-intelligence/feed/",
        feed_name="TechCrunch AI",
        published_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        summary="OpenAI launches agents for enterprise workflows.",
    )

    html = generator.generate_email_html(
        {"AI Top 10": "1. **OpenAI launches new agent platform** ([Source](https://techcrunch.com/openai-agent))\nSummary"},
        datetime(2025, 1, 1, tzinfo=timezone.utc),
        articles_by_collection={"AI Top 10": [article]},
    )

    assert "article-feedback" in html
    assert "多一点" in html
    assert "少一点" in html
    assert "少来源" in html

    href_start = html.index("mailto:feedback@example.com?")
    href = unescape(html[href_start:].split('"', 1)[0])
    parsed = urlparse(href)
    params = parse_qs(parsed.query)
    body = params["body"][0]

    assert params["subject"] == ["Re: MorningModel Feedback"]
    assert body.startswith("晨报反馈：栏目=AI Top 10")
    assert "优先" in body
