import json
from dataclasses import dataclass, field
from typing import Any, Dict, List

from agentcore.events import Event


def _to_openai_tool_calls(calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {"id": c["id"], "type": "function",
         "function": {"name": c["name"], "arguments": c["arguments"]}}
        for c in calls
    ]


@dataclass
class Agent:
    name: str
    role: str
    system_prompt: str
    model: str
    tool_names: List[str] = field(default_factory=list)
    max_tool_rounds: int = 4

    def run(self, task, llm, registry, bus, ledger, context: str = "") -> str:
        messages: List[Dict[str, Any]] = [{"role": "system", "content": self.system_prompt}]
        if context:
            messages.append({"role": "user", "content": context})
        messages.append({"role": "user", "content": task})

        bus.emit(Event(type="phase", agent=self.name, data={"status": "start"}))
        tools_schema = registry.schemas(self.tool_names) if self.tool_names else None

        def on_token(t: str) -> None:
            bus.emit(Event(type="token", agent=self.name, data={"text": t}))

        for _ in range(self.max_tool_rounds):
            assistant = llm.chat(model=self.model, messages=messages,
                                 tools=tools_schema, on_token=on_token)
            calls = assistant.get("tool_calls") or []

            if calls:
                messages.append({"role": "assistant",
                                 "content": assistant.get("content") or "",
                                 "tool_calls": _to_openai_tool_calls(calls)})
            else:
                messages.append({"role": "assistant",
                                 "content": assistant.get("content") or ""})
                text = assistant.get("content") or ""
                bus.emit(Event(type="message", agent=self.name, data={"text": text}))
                return text

            for call in calls:
                try:
                    args = json.loads(call["arguments"] or "{}")
                except json.JSONDecodeError as exc:
                    args = {}
                    bus.emit(Event(type="error", agent=self.name,
                                   data={"tool": call["name"],
                                         "error": "malformed tool arguments: " + str(exc)}))
                bus.emit(Event(type="tool_call", agent=self.name,
                               data={"tool": call["name"], "args": args}))
                try:
                    result = registry.get(call["name"]).fn(**args)
                    ledger.record(call["name"], args, result)
                    bus.emit(Event(type="tool_result", agent=self.name,
                                   data={"tool": call["name"], "result": result}))
                    content = json.dumps(result, ensure_ascii=False, default=str)
                except Exception as exc:  # tool failure must not crash the debate
                    content = json.dumps({"error": str(exc)})
                    bus.emit(Event(type="error", agent=self.name,
                                   data={"tool": call["name"], "error": str(exc)}))
                messages.append({"role": "tool", "tool_call_id": call["id"],
                                 "content": content})

        bus.emit(Event(type="message", agent=self.name,
                       data={"text": "(stopped: max tool rounds reached)"}))
        return ""
