from dataclasses import dataclass
from typing import Any, Callable, Dict, List


@dataclass
class Tool:
    name: str
    description: str
    parameters: Dict[str, Any]   # JSON Schema for the function arguments
    fn: Callable[..., Any]

    def to_openai_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError("Tool not registered: " + name)
        return self._tools[name]

    def schemas(self, names: List[str]) -> List[Dict[str, Any]]:
        return [self._tools[n].to_openai_schema() for n in names]
