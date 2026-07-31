from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import feedparser

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
