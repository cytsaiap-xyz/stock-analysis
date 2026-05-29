import os
import time
from typing import Any, Callable, Dict, List, Optional


def _is_transient(exc: Exception) -> bool:
    """True for errors worth retrying: HTTP 429 / 5xx, timeouts, connection drops."""
    status = getattr(exc, "status_code", None)
    if status is not None and (status == 429 or status >= 500):
        return True
    return type(exc).__name__ in ("APITimeoutError", "APIConnectionError")


class LLMClient:
    """Model-agnostic wrapper over the NVIDIA OpenAI-compatible endpoint.

    Streams content tokens (via on_token) and assembles tool-call fragments
    into a normalized assistant message:
        {"role": "assistant", "content": Optional[str], "tool_calls": [
            {"id": str, "name": str, "arguments": str(json)} ]}
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://integrate.api.nvidia.com/v1",
        client: Any = None,
        api_key_env: str = "NVIDIA_API_KEY",
    ) -> None:
        if client is not None:
            self._client = client
            return
        key = api_key or os.environ.get(api_key_env)
        if not key:
            raise RuntimeError("{} is not set".format(api_key_env))
        from openai import OpenAI

        self._client = OpenAI(base_url=base_url, api_key=key)

    def chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        on_token: Optional[Callable[[str], None]] = None,
        temperature: float = 0.6,
        max_tokens: int = 1024,
        max_retries: int = 3,
        backoff: float = 1.0,
    ) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = dict(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        # Retry transient errors (429 / 5xx / timeouts) with exponential backoff.
        # The NVIDIA free tier returns 504s under load; one shouldn't kill a run.
        attempt = 0
        while True:
            try:
                stream = self._client.chat.completions.create(**kwargs)
                break
            except Exception as exc:
                if attempt >= max_retries or not _is_transient(exc):
                    raise
                time.sleep(backoff * (2 ** attempt))
                attempt += 1
        content_parts: List[str] = []
        acc: Dict[int, Dict[str, str]] = {}

        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            text = getattr(delta, "content", None)
            if text:
                content_parts.append(text)
                if on_token:
                    on_token(text)
            for tc in (getattr(delta, "tool_calls", None) or []):
                slot = acc.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
                if getattr(tc, "id", None):
                    slot["id"] = tc.id
                fn = getattr(tc, "function", None)
                if fn is not None:
                    if getattr(fn, "name", None):
                        slot["name"] = fn.name
                    if getattr(fn, "arguments", None):
                        slot["arguments"] += fn.arguments

        tool_calls = [acc[i] for i in sorted(acc)]
        content = "".join(content_parts) if content_parts else None
        return {"role": "assistant", "content": content, "tool_calls": tool_calls}
