from agentcore.events import Event
from main import TerminalRenderer


def test_grounding_flag_does_not_crash_terminal_renderer():
    renderer = TerminalRenderer()
    # Unknown/unhandled event types fall through the if/elif chain silently.
    renderer(Event(type="grounding_flag", agent="fundamental", data={"unsupported": [30.52]}))


def test_terminal_renderer_prints_unstreamed_message(capsys):
    r = TerminalRenderer()
    r(Event(type="message", agent="fundamental", data={"text": "動態發言"}))
    out = capsys.readouterr().out
    assert "fundamental" in out and "動態發言" in out


def test_terminal_renderer_does_not_duplicate_streamed_message(capsys):
    r = TerminalRenderer()
    r(Event(type="token", agent="technical", data={"text": "已"}))
    r(Event(type="token", agent="technical", data={"text": "串流"}))
    r(Event(type="message", agent="technical", data={"text": "已串流"}))
    out = capsys.readouterr().out
    assert out.count("已串流") == 1   # streamed once; message must not re-print it


def test_terminal_renderer_prints_grounding_flag(capsys):
    r = TerminalRenderer()
    r(Event(type="grounding_flag", agent="risk", data={"unsupported": [30.52]}))
    out = capsys.readouterr().out
    assert "30.52" in out
