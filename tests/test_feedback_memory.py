from datetime import datetime, timezone

from better_morning.feedback_memory import FeedbackMemory
from better_morning.rss_fetcher import Article


def _article(title: str, link: str, summary: str = "summary") -> Article:
    return Article(
        id=link,
        title=title,
        link=link,
        published_date=datetime.now(timezone.utc),
        summary=summary,
        feed_name="Test Feed",
    )


def test_feedback_memory_can_score_source_and_topic(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    memory = FeedbackMemory("AI Top 10")
    memory.record_source_feedback("techcrunch.com", "deprioritize", "重复多", collection_name="AI Top 10")
    memory.record_topic_feedback("agents", "prefer", "值得长期跟踪", collection_name="AI Top 10")

    article = _article("Agents reshape enterprise workflow", "https://techcrunch.com/story")
    source_only = _article("Enterprise workflow reshapes operations", "https://techcrunch.com/story-2")

    assert memory.source_action("techcrunch.com") == "deprioritize"
    assert memory.topic_score("agents") > 0
    assert memory.article_feedback_score(source_only) < 0
    assert memory.article_feedback_score(article) >= memory.article_feedback_score(source_only)


def test_feedback_memory_can_block_article(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    memory = FeedbackMemory("AI Top 10")
    memory.record_source_feedback("badsource.com", "block", "标题党", collection_name="AI Top 10")

    article = _article("Wild exclusive rumor", "https://badsource.com/story")
    assert memory.article_is_blocked(article) is True
