from agentcore.events import Event
from gui import format_event


def test_message_renders_with_agent_tag():
    out = format_event(Event(type="message", agent="fundamental", data={"text": "hi"}))
    assert out == ("[fundamental] hi\n", "fundamental")


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
    assert "RESEARCH" in text and tag == "system"


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
