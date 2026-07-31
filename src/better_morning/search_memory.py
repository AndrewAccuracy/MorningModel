from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .article_utils import extract_domain, extract_topic_keywords
from .rss_fetcher import Article


@dataclass
class ScopePlan:
    curated_articles: list[Article]
    fetch_budget: int
    exploration_articles: list[Article]


class SearchMemory:
    """Lightweight local memory for adaptive source and topic weighting."""

    def __init__(
        self,
        collection_name: str,
        history_dir: str = "history",
        lookback_days: int = 7,
    ):
        self.collection_name = collection_name
        self.lookback_days = lookback_days
        self.history_dir = Path(history_dir)
        self.history_dir.mkdir(exist_ok=True)
        self.path = self.history_dir / "search_memory.json"
        self.data = self._load()
        self.collection_state = self.data.setdefault("collections", {}).setdefault(
            collection_name,
            {
                "sources": {},
                "topics": {},
                "updated_at": None,
            },
        )
        self._prune_stale_entries()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"collections": {}}
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return {"collections": {}}

    def save(self) -> None:
        self.collection_state["updated_at"] = datetime.now(timezone.utc).isoformat()
        with self.path.open("w", encoding="utf-8") as fh:
            json.dump(self.data, fh, indent=2, ensure_ascii=False)

    def _parse_dt(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    def _prune_stale_entries(self) -> None:
        """Keep automatic memory bounded to the configured rolling window."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.lookback_days)
        cutoff_date = cutoff.date().isoformat()
        for key in ("sources", "topics"):
            bucket = self.collection_state.setdefault(key, {})
            stale = [
                name
                for name, stats in bucket.items()
                if self._parse_dt(stats.get("last_seen"))
                and self._parse_dt(stats.get("last_seen")) < cutoff
            ]
            for name in stale:
                del bucket[name]
            for stats in bucket.values():
                daily = stats.get("daily")
                if not isinstance(daily, dict):
                    continue
                for day in list(daily):
                    if day < cutoff_date:
                        del daily[day]

    def _today_key(self) -> str:
        return datetime.now(timezone.utc).date().isoformat()

    def _increment_daily(
        self,
        stats: dict[str, Any],
        field: str,
        amount: int = 1,
    ) -> None:
        """Record a metric in today's bucket while preserving legacy totals."""
        day_stats = stats.setdefault("daily", {}).setdefault(self._today_key(), {})
        day_stats[field] = day_stats.get(field, 0) + amount

    def _recent_counts(self, stats: dict[str, Any]) -> dict[str, int]:
        """Aggregate source/topic metrics across the active lookback window."""
        daily = stats.get("daily")
        if not isinstance(daily, dict):
            return {
                "seen": stats.get("seen", 0),
                "selected": stats.get("selected", 0),
                "content_success": stats.get("fetch_success", 0),
                "content_failure": stats.get("fetch_failure", 0),
                "feed_success": stats.get("feed_success", 0),
                "feed_failure": stats.get("feed_failure", 0),
            }

        cutoff = datetime.now(timezone.utc).date() - timedelta(days=self.lookback_days)
        counts = {
            "seen": 0,
            "selected": 0,
            "content_success": 0,
            "content_failure": 0,
            "feed_success": 0,
            "feed_failure": 0,
        }
        for day, day_stats in daily.items():
            try:
                day_date = datetime.fromisoformat(day).date()
            except ValueError:
                continue
            if day_date < cutoff:
                continue
            for field in counts:
                counts[field] += int(day_stats.get(field, 0) or 0)
        return counts

    def _ensure_source_stats(self, source_key: str) -> dict[str, Any]:
        return self.collection_state.setdefault("sources", {}).setdefault(
            source_key,
            {
                "seen": 0,
                "selected": 0,
                "fetch_success": 0,
                "fetch_failure": 0,
                "feed_success": 0,
                "feed_failure": 0,
                "last_seen": None,
                "last_selected": None,
            },
        )

    def _ensure_topic_stats(self, topic: str) -> dict[str, Any]:
        return self.collection_state.setdefault("topics", {}).setdefault(
            topic,
            {
                "seen": 0,
                "selected": 0,
                "last_seen": None,
                "last_selected": None,
            },
        )

    def _article_source_key(self, article: Article) -> str:
        return extract_domain(str(article.source_url or article.link))

    def _article_topics(self, article: Article) -> list[str]:
        return extract_topic_keywords(article.title, article.summary)

    def record_observed_articles(self, articles: list[Article]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        for article in articles:
            source_stats = self._ensure_source_stats(self._article_source_key(article))
            source_stats["seen"] += 1
            self._increment_daily(source_stats, "seen")
            source_stats["last_seen"] = now
            for topic in self._article_topics(article):
                topic_stats = self._ensure_topic_stats(topic)
                topic_stats["seen"] += 1
                self._increment_daily(topic_stats, "seen")
                topic_stats["last_seen"] = now

    def record_processed_articles(self, articles: list[Article]) -> None:
        for article in articles:
            source_stats = self._ensure_source_stats(self._article_source_key(article))
            if article.content or article.raw_content:
                source_stats["fetch_success"] += 1
                self._increment_daily(source_stats, "content_success")
            else:
                source_stats["fetch_failure"] += 1
                self._increment_daily(source_stats, "content_failure")

    def record_feed_fetch_report(self, fetch_report: dict[str, Any]) -> None:
        """Persist feed-level reliability before article-level filtering begins."""
        now = datetime.now(timezone.utc).isoformat()
        for feed in fetch_report.get("successful", []):
            source_key = extract_domain(str(feed.get("url", "")))
            if not source_key:
                continue
            source_stats = self._ensure_source_stats(source_key)
            source_stats["feed_success"] += 1
            source_stats["last_seen"] = now
            self._increment_daily(source_stats, "feed_success")

        for feed in fetch_report.get("failed", []):
            source_key = extract_domain(str(feed.get("url", "")))
            if not source_key:
                continue
            source_stats = self._ensure_source_stats(source_key)
            source_stats["feed_failure"] += 1
            source_stats["last_seen"] = now
            self._increment_daily(source_stats, "feed_failure")

    def record_selected_articles(self, articles: list[Article]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        for article in articles:
            source_stats = self._ensure_source_stats(self._article_source_key(article))
            source_stats["selected"] += 1
            self._increment_daily(source_stats, "selected")
            source_stats["last_selected"] = now
            for topic in self._article_topics(article):
                topic_stats = self._ensure_topic_stats(topic)
                topic_stats["selected"] += 1
                self._increment_daily(topic_stats, "selected")
                topic_stats["last_selected"] = now

    def source_quality_metrics(self, source_key: str) -> dict[str, float | int]:
        """Return recent source health and hit-rate metrics used for weighting."""
        stats = self.collection_state.get("sources", {}).get(source_key, {})
        counts = self._recent_counts(stats)
        seen = counts["seen"]
        selected = counts["selected"]
        content_success = counts["content_success"]
        content_failure = counts["content_failure"]
        feed_success = counts["feed_success"]
        feed_failure = counts["feed_failure"]
        feed_total = feed_success + feed_failure
        content_total = content_success + content_failure
        return {
            **counts,
            "selection_rate": selected / max(seen, 1),
            "feed_success_rate": feed_success / max(feed_total, 1),
            "content_success_rate": content_success / max(content_total, 1),
        }

    def article_memory_score(self, article: Article) -> float:
        source_key = self._article_source_key(article)
        metrics = self.source_quality_metrics(source_key)
        seen = int(metrics["seen"])
        selected = int(metrics["selected"])
        content_success = int(metrics["content_success"])
        content_failure = int(metrics["content_failure"])
        feed_success = int(metrics["feed_success"])
        feed_failure = int(metrics["feed_failure"])

        score = 0.0
        if seen >= 3:
            hit_rate = float(metrics["selection_rate"])
            if hit_rate >= 0.5:
                score += 2.5
            elif hit_rate <= 0.15:
                score -= 2.0

        feed_total = feed_success + feed_failure
        if feed_total >= 3:
            feed_rate = float(metrics["feed_success_rate"])
            if feed_rate >= 0.8:
                score += 1.0
            elif feed_rate <= 0.5:
                score -= 1.5

        content_total = content_success + content_failure
        if content_total >= 3:
            content_rate = float(metrics["content_success_rate"])
            if content_rate >= 0.7:
                score += 1.0
            elif content_rate <= 0.35:
                score -= 1.0

        hot_topic_hits = 0
        cold_topic_hits = 0
        for topic in self._article_topics(article):
            topic_stats = self.collection_state.get("topics", {}).get(topic, {})
            topic_seen = topic_stats.get("seen", 0)
            topic_selected = topic_stats.get("selected", 0)
            if topic_selected >= 2 and topic_selected >= max(1, topic_seen // 2):
                hot_topic_hits += 1
            elif topic_seen >= 3 and topic_selected == 0:
                cold_topic_hits += 1

        score += min(2.0, hot_topic_hits * 0.8)
        score -= min(1.5, cold_topic_hits * 0.5)
        return score

    def plan_scope(self, articles: list[Article], base_fetch_budget: int) -> ScopePlan:
        if not articles:
            return ScopePlan([], 0, [])

        ranked = sorted(
            articles,
            key=lambda article: self.article_memory_score(article),
            reverse=True,
        )

        hot_topic_articles = [
            article for article in ranked if self.article_memory_score(article) >= 1.5
        ]
        fetch_budget = min(
            len(ranked),
            base_fetch_budget + min(3, max(0, len(hot_topic_articles) // 2)),
        )

        candidate_window = min(
            len(ranked),
            max(fetch_budget + 4, fetch_budget * 2),
        )
        candidate_pool = ranked[:candidate_window]

        # Enforce diversity so the system does not collapse into a few repeat domains.
        curated: list[Article] = []
        source_counts: dict[str, int] = {}
        hot_topic_counts: dict[str, int] = {}
        deferred: list[Article] = []
        for article in candidate_pool:
            source_key = self._article_source_key(article)
            topics = self._article_topics(article)
            source_cap = 2 if self.article_memory_score(article) >= 1.5 else 1
            repeated_hot_topics = sum(
                1 for topic in topics if hot_topic_counts.get(topic, 0) >= 2
            )
            if source_counts.get(source_key, 0) >= source_cap or repeated_hot_topics >= 2:
                deferred.append(article)
                continue
            curated.append(article)
            source_counts[source_key] = source_counts.get(source_key, 0) + 1
            for topic in topics:
                hot_topic_counts[topic] = hot_topic_counts.get(topic, 0) + 1

        for article in deferred:
            if len(curated) >= candidate_window:
                break
            source_key = self._article_source_key(article)
            source_cap = 2 if self.article_memory_score(article) >= 1.5 else 1
            if source_counts.get(source_key, 0) >= source_cap:
                continue
            curated.append(article)
            source_counts[source_key] = source_counts.get(source_key, 0) + 1

        # Keep a small exploration lane so new sources can still prove themselves.
        exploration: list[Article] = []
        seen_sources = {
            self._article_source_key(article)
            for article in curated
        }
        for article in ranked[candidate_window:]:
            source_key = self._article_source_key(article)
            source_stats = self.collection_state.get("sources", {}).get(source_key, {})
            if source_key in seen_sources:
                continue
            if source_stats.get("seen", 0) > 1:
                continue
            exploration.append(article)
            seen_sources.add(source_key)
            if len(exploration) >= 2:
                break

        final_curated = curated + exploration
        return ScopePlan(
            final_curated,
            min(len(final_curated), fetch_budget),
            exploration,
        )

    def build_debug_report(self, plan: ScopePlan | None = None) -> str:
        sources = self.collection_state.get("sources", {})
        topics = self.collection_state.get("topics", {})

        def _source_score(item: tuple[str, dict[str, Any]]) -> tuple[float, int]:
            source_key, _ = item
            metrics = self.source_quality_metrics(source_key)
            selected = int(metrics["selected"])
            hit_rate = float(metrics["selection_rate"])
            return (hit_rate, selected)

        def _topic_score(item: tuple[str, dict[str, Any]]) -> tuple[int, int]:
            _, stats = item
            counts = self._recent_counts(stats)
            return (counts.get("selected", 0), counts.get("seen", 0))

        top_sources = sorted(
            sources.items(),
            key=_source_score,
            reverse=True,
        )[:5]
        top_topics = sorted(
            topics.items(),
            key=_topic_score,
            reverse=True,
        )[:7]

        lines = [
            f"### Search Memory Debug · {self.collection_name}",
            "",
            f"- Lookback window: {self.lookback_days} days",
            f"- Tracked sources: {len(sources)}",
            f"- Tracked topics: {len(topics)}",
        ]

        if plan is not None:
            source_diversity = len(
                {self._article_source_key(article) for article in plan.curated_articles}
            )
            lines.extend(
                [
                    f"- Planned fetch budget: {plan.fetch_budget}",
                    f"- Candidate window after memory shaping: {len(plan.curated_articles)}",
                    f"- Exploration picks reserved: {len(plan.exploration_articles)}",
                    f"- Source diversity in candidate window: {source_diversity}",
                ]
            )

        if top_sources:
            lines.extend(["", "#### High-Signal Sources", ""])
            for source_key, _ in top_sources:
                metrics = self.source_quality_metrics(source_key)
                seen = int(metrics["seen"])
                selected = int(metrics["selected"])
                feed_success = int(metrics["feed_success"])
                feed_failure = int(metrics["feed_failure"])
                content_success = int(metrics["content_success"])
                content_failure = int(metrics["content_failure"])
                hit_rate = float(metrics["selection_rate"])
                feed_rate = float(metrics["feed_success_rate"])
                content_rate = float(metrics["content_success_rate"])
                lines.append(
                    f"- `{source_key}` · selected={hit_rate:.0%} ({selected}/{seen}) · feed_ok={feed_rate:.0%} ({feed_success}/{feed_success + feed_failure}) · content_ok={content_rate:.0%} ({content_success}/{content_success + content_failure})"
                )

        if top_topics:
            lines.extend(["", "#### Hot Topics", ""])
            for topic, stats in top_topics:
                counts = self._recent_counts(stats)
                lines.append(
                    f"- `{topic}` · selected={counts.get('selected', 0)} · seen={counts.get('seen', 0)}"
                )

        lines.extend(
            [
                "",
                "#### Guardrails",
                "",
                "- We do not optimize only for hit rate; source and topic diversity are preserved intentionally.",
                "- Exploration slots remain open for low-history or new sources, so the system can still discover new signal.",
                "- Sources with weak recent selection or fetch stability receive lower priority and tighter per-source caps.",
                "- High-traffic or repeatedly cited stories can still win, but they should not crowd out every other angle.",
            ]
        )

        return "\n".join(lines)
