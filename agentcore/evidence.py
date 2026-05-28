from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class EvidenceEntry:
    tool: str
    args: Dict[str, Any]
    result: Any


class EvidenceLedger:
    def __init__(self) -> None:
        self._entries: List[EvidenceEntry] = []

    def record(self, tool: str, args: Dict[str, Any], result: Any) -> None:
        self._entries.append(EvidenceEntry(tool=tool, args=dict(args), result=result))

    def entries(self) -> List[EvidenceEntry]:
        return list(self._entries)
