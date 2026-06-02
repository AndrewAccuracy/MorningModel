from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import urlparse


COMMON_TITLE_NOISE = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "of",
    "for",
    "in",
    "on",
    "at",
    "with",
    "from",
    "by",
    "how",
    "why",
    "what",
    "when",
    "latest",
    "new",
    "analysis",
    "opinion",
    "podcast",
    "live",
    "update",
    "today",
    "says",
    "said",
    "announces",
    "announced",
    "launches",
    "launch",
    "introducing",
    "first",
    "after",
    "into",
    "over",
    "its",
    "their",
    "your",
    "you",
    "this",
    "that",
    "these",
    "those",
}

SPECULATIVE_TERMS = {
    "reportedly",
    "report",
    "rumor",
    "rumour",
    "could",
    "might",
    "may",
    "seems",
    "suggests",
    "allegedly",
    "unconfirmed",
}

LOW_SIGNAL_TERMS = {
    "sponsored",
    "promo",
    "press release",
    "guest post",
    "affiliate",
    "beginner guide",
    "explained",
    "tutorial",
    "personal finance",
}

HIGH_IMPACT_TERMS = {
    "acquisition",
    "agent",
    "antitrust",
    "approval",
    "bankruptcy",
    "central bank",
    "earnings",
    "ecb",
    "federal reserve",
    "fed",
    "funding",
    "gdp",
    "guidance",
    "inflation",
    "ipo",
    "layoffs",
    "lawsuit",
    "merger",
    "model",
    "openai",
    "policy",
    "rates",
    "regulation",
    "release",
    "revenue",
    "sanctions",
    "search",
    "security",
    "tariff",
    "treasury",
}


def extract_domain(url: str) -> str:
    try:
        return urlparse(str(url)).netloc.lower()
    except Exception:
        return ""


def normalize_title(title: str) -> str:
    normalized = (title or "").lower()
    normalized = re.sub(r"\[[^\]]+\]", " ", normalized)
    normalized = re.sub(r"\([^\)]*\)", " ", normalized)
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def title_tokens(title: str) -> list[str]:
    tokens = [
        token
        for token in normalize_title(title).split()
        if token
        and token not in COMMON_TITLE_NOISE
        and (len(token) > 2 or token.isdigit())
    ]
    return tokens


def extract_topic_keywords(title: str, summary: str | None = None, limit: int = 5) -> list[str]:
    combined = " ".join(part for part in [title or "", summary or ""] if part)
    tokens = title_tokens(combined)
    ordered_unique: list[str] = []
    seen = set()
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        ordered_unique.append(token)
        if len(ordered_unique) >= limit:
            break
    return ordered_unique


def title_signature(title: str) -> str:
    return normalize_title(title)


def title_similarity(title_a: str, title_b: str) -> float:
    normalized_a = normalize_title(title_a)
    normalized_b = normalize_title(title_b)
    if normalized_a and normalized_a == normalized_b:
        return 1.0

    tokens_a = set(title_tokens(title_a))
    tokens_b = set(title_tokens(title_b))
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a & tokens_b)
    if intersection < 2:
        return 0.0
    union = len(tokens_a | tokens_b)
    if union == 0:
        return 0.0
    return intersection / union


def _matches_any(text: str, phrases: Iterable[str]) -> bool:
    lowered = (text or "").lower()
    return any(phrase in lowered for phrase in phrases)


def infer_source_scores(
    domain: str,
    feed_name: str | None = None,
    credibility_override: int | None = None,
    readership_override: int | None = None,
) -> tuple[int, int]:
    if credibility_override is not None or readership_override is not None:
        return credibility_override or 3, readership_override or 3

    feed_name_l = (feed_name or "").lower()
    domain = (domain or "").lower()

    if any(
        trusted in domain
        for trusted in (
            "federalreserve.gov",
            "bis.org",
            "openai.com",
            "anthropic.com",
            "googleblog.com",
            "deepmind.google",
            "huggingface.co",
            "arxiv.org",
            "export.arxiv.org",
            "jmlr.org",
            "jair.org",
        )
    ):
        return 5, 4

    if any(
        trusted in domain
        for trusted in (
            "ft.com",
            "wsj.com",
            "dowjones.io",
            "cnbc.com",
            "marketwatch.com",
            "techcrunch.com",
            "theverge.com",
            "infoq.com",
        )
    ):
        return 5, 5

    if any(
        trusted in domain
        for trusted in (
            "towardsdatascience.com",
            "alignmentforum.org",
            "aisnakeoil.com",
            "understandingai.org",
            "latent.space",
            "interconnects.ai",
            "oneusefulthing.org",
            "apricitas.io",
            "theovershoot.co",
            "netinterest.co",
            "noahpinion.blog",
        )
    ):
        return 4, 3

    if "medium.com" in domain or "substack.com" in domain or "blog" in domain:
        return 2, 1

    if "press release" in feed_name_l:
        return 5, 3

    return 3, 2


def estimate_article_quality_signals(title: str, summary: str | None) -> tuple[bool, bool]:
    joined = " ".join(part for part in [title or "", summary or ""] if part)
    speculative = _matches_any(joined, SPECULATIVE_TERMS)
    low_signal = _matches_any(joined, LOW_SIGNAL_TERMS)
    return speculative, low_signal


def impact_keyword_score(title: str, summary: str | None) -> float:
    joined = " ".join(part for part in [title or "", summary or ""] if part).lower()
    matches = sum(1 for phrase in HIGH_IMPACT_TERMS if phrase in joined)
    return min(4.0, matches * 0.75)
