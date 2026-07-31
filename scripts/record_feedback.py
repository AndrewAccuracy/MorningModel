#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from better_morning.feedback_memory import FeedbackMemory


def main() -> int:
    parser = argparse.ArgumentParser(description="Record manual source/topic feedback for Better Morning.")
    parser.add_argument("--collection", default=None, help='Optional collection scope, e.g. "AI Top 10".')
    parser.add_argument("--kind", choices=["source", "topic"], required=True)
    parser.add_argument("--target", required=True, help="Domain like techcrunch.com or topic like agents")
    parser.add_argument("--action", required=True, help="Source: trust/watch/deprioritize/block. Topic: prefer/watch/deprioritize/block")
    parser.add_argument("--reason", required=True, help="Human reason for the feedback")
    args = parser.parse_args()

    memory = FeedbackMemory(args.collection or "global")
    if args.kind == "source":
        memory.record_source_feedback(
            args.target,
            args.action,
            args.reason,
            collection_name=args.collection,
        )
    else:
        memory.record_topic_feedback(
            args.target,
            args.action,
            args.reason,
            collection_name=args.collection,
        )
    memory.save()

    scope = args.collection or "global"
    print(f"Recorded {args.kind} feedback for '{args.target}' in scope '{scope}' with action '{args.action}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
