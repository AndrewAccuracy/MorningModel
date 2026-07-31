from __future__ import annotations

import re
from dataclasses import dataclass


FEEDBACK_PREFIX = "晨报反馈："

SOURCE_ACTION_ALIASES = {
    "优先": "trust",
    "保留": "trust",
    "信任": "trust",
    "观察": "watch",
    "关注": "watch",
    "降权": "deprioritize",
    "压一压": "deprioritize",
    "少看": "deprioritize",
    "重复太多": "deprioritize",
    "拉黑": "block",
    "屏蔽": "block",
    "封禁": "block",
}

TOPIC_ACTION_ALIASES = {
    "优先": "prefer",
    "继续跟": "prefer",
    "重点跟踪": "prefer",
    "观察": "watch",
    "关注": "watch",
    "降权": "deprioritize",
    "压一压": "deprioritize",
    "减少": "deprioritize",
    "拉黑": "block",
    "屏蔽": "block",
}


@dataclass
class ParsedFeedback:
    collection: str | None
    kind: str
    target: str
    action: str
    reason: str


def extract_prefixed_feedback_block(text: str) -> str | None:
    """Find the machine-readable feedback line inside a free-form email reply."""
    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped.startswith(FEEDBACK_PREFIX):
            return stripped[len(FEEDBACK_PREFIX):].strip()
    return None


def _match_action(text: str, aliases: dict[str, str]) -> str | None:
    for phrase, action in aliases.items():
        if phrase in text:
            return action
    return None


def parse_feedback_line(line: str) -> ParsedFeedback | None:
    """Parse one compact source/topic preference from Chinese or English labels."""
    text = line.strip()
    if not text:
        return None

    collection = None
    if "栏目=" in text:
        match = re.search(r"栏目=([^;；]+)", text)
        if match:
            collection = match.group(1).strip()

    source_match = re.search(r"(来源|source)\s*[:：=]?\s*([a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})", text, re.IGNORECASE)
    if source_match:
        target = source_match.group(2).lower()
        action = _match_action(text, SOURCE_ACTION_ALIASES)
        if not action:
            return None
        return ParsedFeedback(
            collection=collection,
            kind="source",
            target=target,
            action=action,
            reason=text,
        )

    topic_match = re.search(r"(主题|topic)\s*[:：=]?\s*([\w\u4e00-\u9fff\-\s]+)", text, re.IGNORECASE)
    if topic_match:
        target = topic_match.group(2).strip()
        target = re.split(r"(优先|继续跟|重点跟踪|观察|关注|降权|压一压|减少|拉黑|屏蔽|理由[:：=])", target, maxsplit=1)[0]
        target = target.strip().lower()
        action = _match_action(text, TOPIC_ACTION_ALIASES)
        if not action:
            return None
        return ParsedFeedback(
            collection=collection,
            kind="topic",
            target=target,
            action=action,
            reason=text,
        )

    return None


def parse_feedback_email(text: str) -> list[ParsedFeedback]:
    """Parse all actionable feedback items from an email body."""
    block = extract_prefixed_feedback_block(text)
    if not block:
        return []

    parts = [segment.strip() for segment in re.split(r"[|\n]+", block) if segment.strip()]
    parsed: list[ParsedFeedback] = []
    for part in parts:
        item = parse_feedback_line(part)
        if item:
            parsed.append(item)
    return parsed
