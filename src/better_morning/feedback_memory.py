from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .article_utils import extract_domain, extract_topic_keywords
from .rss_fetcher import Article


SOURCE_ACTION_SCORES = {
    "trust": 3.0,
    "watch": 1.0,
    "deprioritize": -2.0,
    "block": -100.0,
}

TOPIC_ACTION_SCORES = {
    "prefer": 2.0,
    "watch": 0.5,
    "deprioritize": -1.5,
    "block": -100.0,
}


class FeedbackMemory:
    """Human feedback memory layered on top of automatic statistics."""

    def __init__(self, collection_name: str, history_dir: str = "history"):
        self.collection_name = collection_name
        self.history_dir = Path(history_dir)
        self.history_dir.mkdir(exist_ok=True)
        self.path = self.history_dir / "feedback_memory.json"
        self.data = self._load()
        self.data.setdefault("global", {"sources": {}, "topics": {}})
        self.data.setdefault("collections", {})
        self.collection_state = self.data["collections"].setdefault(
            collection_name,
            {"sources": {}, "topics": {}},
        )

    def _load(self) -> dict[str, Any]:
        """Load feedback defensively so a corrupt memory file cannot stop a run."""
        if not self.path.exists():
            return {}
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return {}

    def save(self) -> None:
        with self.path.open("w", encoding="utf-8") as fh:
            json.dump(self.data, fh, indent=2, ensure_ascii=False)

    def _bucket(self, kind: str, collection_name: str | None = None) -> dict[str, Any]:
        if collection_name:
            return self.data["collections"].setdefault(
                collection_name,
                {"sources": {}, "topics": {}},
            )[kind]
        return self.data["global"][kind]

    def _entry_for(self, kind: str, target: str) -> dict[str, Any] | None:
        target = target.strip().lower()
        local = self.collection_state.get(kind, {}).get(target)
        if local:
            return local
        return self.data["global"].get(kind, {}).get(target)

    def _record_feedback(
        self,
        *,
        kind: str,
        target: str,
        action: str,
        reason: str,
        collection_name: str | None = None,
    ) -> None:
        """Store the latest preference while retaining a short audit trail."""
        bucket = self._bucket(kind, collection_name)
        target = target.strip().lower()
        now = datetime.now(timezone.utc).isoformat()
        entry = bucket.setdefault(
            target,
            {
                "action": action,
                "reason": reason,
                "feedback_count": 0,
                "updated_at": now,
                "history": [],
            },
        )
        entry["action"] = action
        entry["reason"] = reason
        entry["feedback_count"] = entry.get("feedback_count", 0) + 1
        entry["updated_at"] = now
        history = entry.setdefault("history", [])
        history.append(
            {
                "action": action,
                "reason": reason,
                "updated_at": now,
                "scope": collection_name or "global",
            }
        )
        entry["history"] = history[-10:]

    def record_source_feedback(
        self,
        source: str,
        action: str,
        reason: str,
        collection_name: str | None = None,
    ) -> None:
        if action not in SOURCE_ACTION_SCORES:
            raise ValueError(f"Unsupported source action: {action}")
        self._record_feedback(
            kind="sources",
            target=source,
            action=action,
            reason=reason,
            collection_name=collection_name,
        )

    def record_topic_feedback(
        self,
        topic: str,
        action: str,
        reason: str,
        collection_name: str | None = None,
    ) -> None:
        if action not in TOPIC_ACTION_SCORES:
            raise ValueError(f"Unsupported topic action: {action}")
        self._record_feedback(
            kind="topics",
            target=topic,
            action=action,
            reason=reason,
            collection_name=collection_name,
        )

    def source_action(self, source: str) -> str | None:
        entry = self._entry_for("sources", source)
        return entry.get("action") if entry else None

    def source_score(self, source: str) -> float:
        return SOURCE_ACTION_SCORES.get(self.source_action(source), 0.0)

    def topic_score(self, topic: str) -> float:
        entry = self._entry_for("topics", topic)
        if not entry:
            return 0.0
        return TOPIC_ACTION_SCORES.get(entry.get("action"), 0.0)

    def article_feedback_score(self, article: Article) -> float:
        """Score an article using explicit source and topic preferences."""
        source_key = extract_domain(str(article.source_url or article.link))
        score = self.source_score(source_key)
        for topic in extract_topic_keywords(article.title, article.summary):
            score += self.topic_score(topic)
        return score

    def article_is_blocked(self, article: Article) -> bool:
        """Apply hard blocks before a candidate reaches the LLM selection prompt."""
        source_key = extract_domain(str(article.source_url or article.link))
        if self.source_action(source_key) == "block":
            return True
        for topic in extract_topic_keywords(article.title, article.summary):
            entry = self._entry_for("topics", topic)
            if entry and entry.get("action") == "block":
                return True
        return False

    def build_debug_report(self) -> str:
        def render(title: str, items: dict[str, Any]) -> list[str]:
            lines = [f"#### {title}", ""]
            if not items:
                lines.append("- No manual feedback recorded yet.")
                return lines
            for target, entry in list(items.items())[:8]:
                lines.append(
                    f"- `{target}` · action={entry.get('action')} · reason={entry.get('reason', '')}"
                )
            return lines

        lines = [
            f"### Feedback Memory · {self.collection_name}",
            "",
            "This layer stores explicit human preferences so rules stay flexible and can be corrected over time.",
            "",
        ]
        lines.extend(render("Collection Source Feedback", self.collection_state.get("sources", {})))
        lines.extend([""])
        lines.extend(render("Collection Topic Feedback", self.collection_state.get("topics", {})))
        return "\n".join(lines)
