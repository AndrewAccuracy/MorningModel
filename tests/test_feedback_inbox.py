from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.poll_feedback_inbox import subject_matches_prefix


def test_subject_matches_prefix_accepts_expected_reply_prefix():
    assert subject_matches_prefix(
        "Re: MorningModel Feedback - 2026-05-29",
        ["Re: MorningModel Feedback"],
    ) is True


def test_subject_matches_prefix_rejects_unrelated_subject():
    assert subject_matches_prefix(
        "Re: Random Conversation",
        ["Re: MorningModel Feedback"],
    ) is False
