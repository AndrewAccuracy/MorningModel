from datetime import datetime, timezone

from better_morning.rss_fetcher import Article
from better_morning.search_memory import SearchMemory


def _article(title: str, link: str, summary: str = "summary") -> Article:
    return Article(
        id=link,
        title=title,
        link=link,
        published_date=datetime.now(timezone.utc),
        summary=summary,
        feed_name="Test Feed",
    )


def test_search_memory_boosts_high_hit_sources(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    memory = SearchMemory("AI Top 10")

    strong = _article("OpenAI launches new agent runtime", "https://trusted.com/1")
    weak = _article("Celebrity tutorial explained", "https://weak.com/1")

    for idx in range(4):
        observed = _article(
            f"OpenAI launches new agent runtime {idx}",
            f"https://trusted.com/{idx + 10}",
        )
        memory.record_observed_articles([observed])
        memory.record_processed_articles([observed])
        memory.record_selected_articles([observed])

    for idx in range(4):
        cold = _article(
            f"Beginner guide tutorial {idx}",
            f"https://weak.com/{idx + 10}",
        )
        memory.record_observed_articles([cold])

    assert memory.article_memory_score(strong) > memory.article_memory_score(weak)


def test_search_memory_scope_keeps_exploration_lane(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    memory = SearchMemory("AI Top 10")

    hot_articles = []
    for idx in range(5):
        article = _article(
            f"Google agent update {idx}",
            f"https://hot-source.com/{idx}",
        )
        hot_articles.append(article)
        memory.record_observed_articles([article])
        memory.record_processed_articles([article])
        memory.record_selected_articles([article])

    explorer = _article("New lab releases fresh benchmark", "https://new-source.com/1")
    memory.record_observed_articles([explorer])

    plan = memory.plan_scope(hot_articles + [explorer], base_fetch_budget=3)

    assert explorer in plan.curated_articles
    assert len(plan.exploration_articles) <= 2
    assert plan.fetch_budget >= 3


def test_search_memory_debug_report_mentions_guardrails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    memory = SearchMemory("AI Top 10")
    article = _article("OpenAI agents expand search workflow", "https://alpha.com/1")
    memory.record_observed_articles([article])
    memory.record_processed_articles([article])
    memory.record_selected_articles([article])

    plan = memory.plan_scope([article], base_fetch_budget=1)
    report = memory.build_debug_report(plan)

    assert "Guardrails" in report
    assert "Exploration picks reserved" in report
    assert "source and topic diversity" in report
