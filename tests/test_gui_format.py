from agentcore.events import Event
from gui import detect_lean, format_event, verdict_headline


def test_detect_lean_finds_keyword():
    assert detect_lean("整體偏多,給予 看多") == "看多"
    assert detect_lean("估值偏高,看空") == "看空"
    assert detect_lean("方向不明,中性看待") == "中性"


def test_detect_lean_defaults_when_absent():
    assert detect_lean("沒有明確傾向") == "完成"
    assert detect_lean("") == "完成"


def test_verdict_headline_picks_recommendation_line():
    text = "建議: 持有\n信心: 60%\n理由..."
    assert verdict_headline(text) == "建議: 持有"


def test_verdict_headline_falls_back_to_first_line():
    assert verdict_headline("沒有建議標籤\n第二行") == "沒有建議標籤"


def test_message_renders_with_agent_tag():
    out = format_event(Event(type="message", agent="fundamental", data={"text": "hi"}))
    # Display name is localized to Chinese; the colour tag stays the english key.
    assert out == ("[基本面分析師] hi\n", "fundamental")


def test_tool_call_renders_with_agent_tag():
    out = format_event(Event(type="tool_call", agent="technical",
                             data={"tool": "get_valuation", "args": {"stock_no": "2330"}}))
    text, tag = out
    assert tag == "technical"
    assert "get_valuation" in text and "2330" in text


def test_phase_with_label_renders_as_system():
    out = format_event(Event(type="phase", agent="system",
                             data={"phase": "RESEARCH", "stock": "2330"}))
    text, tag = out
    assert "研究分析" in text and tag == "system"


def test_phase_without_label_is_ignored():
    assert format_event(Event(type="phase", agent="x", data={"status": "start"})) is None


def test_token_is_ignored():
    assert format_event(Event(type="token", agent="x", data={"text": "a"})) is None


def test_verdict_is_ignored_by_feed_formatter():
    # verdict updates the banner, not the feed, so the feed formatter ignores it.
    assert format_event(Event(type="verdict", agent="chair", data={"text": "BUY"})) is None


def test_error_renders_as_system():
    out = format_event(Event(type="error", agent="technical",
                             data={"tool": "get_x", "error": "boom"}))
    text, tag = out
    assert tag == "system" and "boom" in text
