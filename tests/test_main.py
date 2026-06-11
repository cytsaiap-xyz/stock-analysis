from agentcore.events import Event
from main import TerminalRenderer


def test_grounding_flag_does_not_crash_terminal_renderer():
    renderer = TerminalRenderer()
    # Unknown/unhandled event types fall through the if/elif chain silently.
    renderer(Event(type="grounding_flag", agent="fundamental", data={"unsupported": [30.52]}))
