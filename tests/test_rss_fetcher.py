from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import feedparser

from better_morning.config import RSSFeed
from better_morning.rss_fetcher import RSSFetcher


def test_parse_time_span():
    fetcher = RSSFetcher(feeds=[])

    assert fetcher._parse_time_span("2d") == timedelta(days=2)
    assert fetcher._parse_time_span("1h") == timedelta(hours=1)
    assert fetcher._parse_time_span("30m") == timedelta(minutes=30)


def test_is_article_too_old_handles_naive_datetime():
    fetcher = RSSFetcher(feeds=[])

    cutoff = datetime(2025, 1, 2, tzinfo=timezone.utc)
    article_date = datetime(2025, 1, 1)

    assert fetcher._is_article_too_old(article_date, cutoff) is True


def test_fetch_feed_retries_retryable_parser_error_with_requests():
    fetcher = RSSFetcher(feeds=[])
    failed_feed = feedparser.FeedParserDict(
        {
            "entries": [],
            "bozo": True,
            "bozo_exception": Exception(
                "[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred"
            ),
        }
    )
    parsed_feed = feedparser.FeedParserDict({"entries": [{"title": "ok"}]})
    response = MagicMock()
    response.status_code = 200
    response.content = b"<rss><channel><item><title>ok</title></item></channel></rss>"
    response.raise_for_status.return_value = None

    with patch(
        "better_morning.rss_fetcher.feedparser.parse",
        side_effect=[failed_feed, parsed_feed],
    ), patch("better_morning.rss_fetcher.requests.get", return_value=response) as get:
        feed = fetcher._fetch_feed_with_retry("https://example.com/feed.xml")

    assert feed.entries == [{"title": "ok"}]
    get.assert_called_once()


def test_fetch_articles_filters_old_undated_entry_by_url_date(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fetcher = RSSFetcher(
        feeds=[
            RSSFeed(
                url="https://www.bis.org/doclist/all_pressrels.rss",
                name="BIS",
            )
        ]
    )
    old_entry = feedparser.FeedParserDict(
        {
            "title": "Old appointment",
            "link": "https://www.bis.org/press/p260416a.htm",
            "summary": "old item",
        }
    )
    recent_entry = feedparser.FeedParserDict(
        {
            "title": "Recent wage tracker",
            "link": "https://www.ecb.europa.eu/press/pr/date/2026/html/ecb.pr260729~4ad7508d8a.en.html",
            "summary": "recent item",
        }
    )
    feed = feedparser.FeedParserDict({"entries": [old_entry, recent_entry]})

    monkeypatch.setattr(fetcher, "_fetch_feed_with_retry", lambda *args, **kwargs: feed)
    monkeypatch.setattr(
        "better_morning.rss_fetcher.datetime",
        MagicMock(
            wraps=datetime,
            now=MagicMock(return_value=datetime(2026, 8, 2, tzinfo=timezone.utc)),
        ),
    )

    articles = fetcher.fetch_articles("Finance Top 10", max_age="7d")

    assert [article.title for article in articles] == ["Recent wage tracker"]
    assert articles[0].published_date == datetime(2026, 7, 29, tzinfo=timezone.utc)


def test_fetch_articles_skips_undated_entry_when_max_age_enabled(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fetcher = RSSFetcher(
        feeds=[RSSFeed(url="https://example.com/feed.xml", name="Example")]
    )
    undated_entry = feedparser.FeedParserDict(
        {
            "title": "No date",
            "link": "https://example.com/no-date",
            "summary": "undated item",
        }
    )
    feed = feedparser.FeedParserDict({"entries": [undated_entry]})

    monkeypatch.setattr(fetcher, "_fetch_feed_with_retry", lambda *args, **kwargs: feed)

    assert fetcher.fetch_articles("Test", max_age="7d") == []
