#!/usr/bin/env python3
from __future__ import annotations

import argparse
import email
import imaplib
import os
from email.header import decode_header, make_header
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from better_morning.feedback_memory import FeedbackMemory
from better_morning.feedback_parser import FEEDBACK_PREFIX, parse_feedback_email


def decode_mime(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="ignore")
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def extract_text_body(message: email.message.Message) -> str:
    if message.is_multipart():
        parts = []
        for part in message.walk():
            content_type = part.get_content_type()
            if content_type != "text/plain":
                continue
            payload = part.get_payload(decode=True) or b""
            charset = part.get_content_charset() or "utf-8"
            parts.append(payload.decode(charset, errors="ignore"))
        return "\n".join(parts)
    payload = message.get_payload(decode=True) or b""
    charset = message.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="ignore")


def normalize_subject(subject: str) -> str:
    return (subject or "").strip()


def subject_matches_prefix(subject: str, required_prefixes: list[str]) -> bool:
    normalized = normalize_subject(subject).lower()
    prefixes = [prefix.strip().lower() for prefix in required_prefixes if prefix.strip()]
    if not prefixes:
        return True
    return any(normalized.startswith(prefix) for prefix in prefixes)


def main() -> int:
    parser = argparse.ArgumentParser(description="Poll a feedback inbox and store parsed editorial feedback.")
    parser.add_argument("--mailbox", default="INBOX")
    parser.add_argument("--mark-seen", action="store_true", help="Mark messages as seen after processing.")
    args = parser.parse_args()

    host = os.getenv("BETTER_MORNING_FEEDBACK_IMAP_HOST")
    username = os.getenv("BETTER_MORNING_FEEDBACK_IMAP_USERNAME")
    password = os.getenv("BETTER_MORNING_FEEDBACK_IMAP_PASSWORD")
    allowed_senders = {
        item.strip().lower()
        for item in re_split_csv(os.getenv("BETTER_MORNING_FEEDBACK_ALLOWED_SENDERS", ""))
        if item.strip()
    }
    required_subject_prefixes = re_split_csv(
        os.getenv("BETTER_MORNING_FEEDBACK_SUBJECT_PREFIXES", "Re: MorningModel Feedback")
    )

    if not host or not username or not password:
        raise SystemExit("Missing feedback IMAP credentials in environment.")

    client = imaplib.IMAP4_SSL(host)
    client.login(username, password)
    client.select(args.mailbox)

    status, data = client.search(None, "UNSEEN")
    if status != "OK":
        raise SystemExit("Failed to search mailbox.")

    for raw_id in data[0].split():
        status, msg_data = client.fetch(raw_id, "(RFC822)")
        if status != "OK":
            continue
        raw_email = msg_data[0][1]
        message = email.message_from_bytes(raw_email)
        sender = decode_mime(message.get("From"))
        sender_lower = sender.lower()
        if allowed_senders and not any(allowed in sender_lower for allowed in allowed_senders):
            continue

        subject = decode_mime(message.get("Subject"))
        if not subject_matches_prefix(subject, required_subject_prefixes):
            continue
        body = extract_text_body(message)
        if FEEDBACK_PREFIX not in body:
            continue

        parsed_items = parse_feedback_email(body)
        for item in parsed_items:
            memory = FeedbackMemory(item.collection or "global")
            if item.kind == "source":
                memory.record_source_feedback(
                    item.target,
                    item.action,
                    item.reason,
                    collection_name=item.collection,
                )
            else:
                memory.record_topic_feedback(
                    item.target,
                    item.action,
                    item.reason,
                    collection_name=item.collection,
                )
            memory.save()
            print(
                f"Recorded {item.kind} feedback from '{sender}' subject='{subject}' target='{item.target}' action='{item.action}'."
            )

        if args.mark_seen:
            client.store(raw_id, "+FLAGS", "\\Seen")

    client.close()
    client.logout()
    return 0


def re_split_csv(value: str) -> list[str]:
    import re

    return [item for item in re.split(r"[,;\n]+", value or "") if item]


if __name__ == "__main__":
    raise SystemExit(main())
