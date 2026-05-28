"""Generic event collector used to build post-run reports.

A `ReportCollector` is just an EventBus subscriber that buffers every Event for
later rendering. It also pulls out the final verdict text and the verification
grounding summary so a renderer can show them prominently.
"""
from typing import Any, Dict, List, Optional

from agentcore.events import Event


class ReportCollector:
    def __init__(self) -> None:
        self.events: List[Event] = []
        self.verdict_text: Optional[str] = None
        self.grounding: Optional[Dict[str, Any]] = None

    def __call__(self, e: Event) -> None:
        self.events.append(e)
        if e.type == "verdict":
            self.verdict_text = e.data.get("text", "")
        elif e.type == "verification":
            g = e.data.get("grounding")
            # Prefer the "final" grounding (after a correction round) if one arrives.
            if g and (self.grounding is None or e.data.get("final")):
                self.grounding = g
