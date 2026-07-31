from better_morning.feedback_parser import FEEDBACK_PREFIX, parse_feedback_email


def test_parse_feedback_email_with_chinese_prefix():
    text = (
        f"{FEEDBACK_PREFIX}栏目=AI Top 10；来源 techcrunch.com 降权，理由：重复多 | "
        "主题 agents 优先，理由：值得长期跟踪"
    )

    parsed = parse_feedback_email(text)

    assert len(parsed) == 2
    assert parsed[0].kind == "source"
    assert parsed[0].target == "techcrunch.com"
    assert parsed[0].action == "deprioritize"
    assert parsed[1].kind == "topic"
    assert parsed[1].target == "agents"
    assert parsed[1].action == "prefer"
