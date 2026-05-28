import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List


@dataclass
class Event:
    type: str            # phase|message|token|tool_call|tool_result|verdict|verification|error
    agent: str           # agent name, or "system"
    data: Dict = field(default_factory=dict)
    ts: float = field(default_factory=time.time)


class EventBus:
    def __init__(self) -> None:
        self._subscribers: List[Callable[[Event], None]] = []

    def subscribe(self, fn: Callable[[Event], None]) -> None:
        self._subscribers.append(fn)

    def emit(self, event: Event) -> None:
        for fn in self._subscribers:
            fn(event)
