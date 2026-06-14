from agentcore.discussion_autogen import (make_selector, bridge_turn,
                                           strip_consensus, is_consensus)
from agentcore.events import EventBus, Event
from agentcore.evidence import EvidenceLedger


class _FakeLLM:
    """Records calls; returns a scripted reply or raises."""
    def __init__(self, reply=None, raises=False):
        self._reply, self._raises = reply, raises
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        if self._raises:
            raise RuntimeError("selector down")
        return {"content": self._reply}


def test_selector_picks_named_speaker():
    names = ["fundamental", "technical", "risk"]
    roles = {"fundamental": "基本面", "technical": "技術面", "risk": "風險"}
    sel = make_selector(names, roles, _FakeLLM(reply="Next: technical."), model="m")
    assert sel([]) == "technical"


def test_selector_falls_back_to_round_robin_on_error():
    names = ["fundamental", "technical"]
    roles = {"fundamental": "基本面", "technical": "技術面"}
    sel = make_selector(names, roles, _FakeLLM(raises=True), model="m")
    assert sel([]) == "fundamental"   # round-robin index 0
    assert sel([]) == "technical"     # index 1
    assert sel([]) == "fundamental"   # wraps


def test_selector_falls_back_when_reply_names_nobody():
    names = ["fundamental", "technical"]
    roles = {"fundamental": "基本面", "technical": "技術面"}
    sel = make_selector(names, roles, _FakeLLM(reply="I am not sure"), model="m")
    assert sel([]) == "fundamental"   # no known name -> round-robin


def test_consensus_helpers_strip_and_detect():
    assert is_consensus("done <CONSENSUS>") is True
    assert is_consensus("still arguing") is False
    assert strip_consensus("agreed <CONSENSUS>") == "agreed"


def test_bridge_turn_emits_message_and_grounding_flag():
    bus, ledger = EventBus(), EvidenceLedger()
    events = []
    bus.subscribe(events.append)
    clean = bridge_turn("fundamental", "PE 約 30.52 偏高 <CONSENSUS>", bus, ledger)
    assert clean == "PE 約 30.52 偏高"                       # sentinel stripped
    msgs = [e for e in events if e.type == "message"]
    assert msgs and msgs[0].agent == "fundamental" and "30.52" in msgs[0].data["text"]
    flags = [e for e in events if e.type == "grounding_flag"]
    assert flags and 30.52 in flags[0].data["unsupported"]   # 30.52 not in (empty) ledger


def test_bridge_turn_grounded_text_has_no_flag():
    bus, ledger = EventBus(), EvidenceLedger()
    events = []
    bus.subscribe(events.append)
    bridge_turn("technical", "維持看多,無新數字", bus, ledger)
    assert not [e for e in events if e.type == "grounding_flag"]
