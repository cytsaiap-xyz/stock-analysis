import os
import time
from typing import Any, Callable, Dict, List, Optional


def _is_transient(exc: Exception) -> bool:
    """True for errors worth retrying: HTTP 429 / 5xx, timeouts, connection drops."""
    status = getattr(exc, "status_code", None)
    if status is not None and (status == 429 or status >= 500):
        return True
    return type(exc).__name__ in ("APITimeoutError", "APIConnectionError")


def _should_try_next_model(exc: Exception) -> bool:
    """Whether to fall back to the next model: transient (429/5xx/timeout) or a
    404 (model unavailable). Non-transient client errors (auth, bad request) are
    NOT masked by a fallback — they re-raise so the real problem surfaces."""
    return _is_transient(exc) or getattr(exc, "status_code", None) == 404


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
            self.base_url = base_url
            self.api_key = None
            return
        key = api_key or os.environ.get(api_key_env)
        if not key:
            raise RuntimeError("{} is not set".format(api_key_env))
        from openai import OpenAI

        self.base_url = base_url
        self.api_key = key
        self._client = OpenAI(base_url=base_url, api_key=key)

    def chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        on_token: Optional[Callable[[str], None]] = None,
        temperature: float = 0.6,
        max_tokens: Optional[int] = None,
        max_retries: int = 3,
        backoff: float = 1.0,
        fallback_models: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        # max_tokens left unset (None) => let the endpoint apply the model's own default
        # output limit (e.g. Gemma's 8K), instead of truncating responses at a fixed cap.
        kwargs: Dict[str, Any] = dict(
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        # Try the primary model, then each fallback in order. Per model, retry
        # transient errors (429 / 5xx / timeouts) with exponential backoff; if a
        # model is still unavailable (429/5xx/404), move to the next. Non-transient
        # errors (auth, bad request) re-raise immediately — a fallback won't fix them.
        models = [model] + list(fallback_models or [])
        stream = None
        last_exc: Optional[Exception] = None
        for idx, mdl in enumerate(models):
            attempt = 0
            while True:
                try:
                    stream = self._client.chat.completions.create(model=mdl, **kwargs)
                    break
                except Exception as exc:
                    last_exc = exc
                    if attempt < max_retries and _is_transient(exc):
                        time.sleep(backoff * (2 ** attempt))
                        attempt += 1
                        continue
                    stream = None
                    break
            if stream is not None:
                break
            is_last = idx == len(models) - 1
            if is_last or not _should_try_next_model(last_exc):
                raise last_exc
        content_parts: List[str] = []
        # Tool-call fragments are assembled in arrival order. OpenAI-style streams
        # carry a per-call `index` (so fragments of the same call share a slot);
        # some OpenAI-compatible endpoints (e.g. Google/Gemini) set index=None and
        # deliver each call complete in one delta — there a delta with a name
        # starts a new call and an argument-only delta continues the current one.
        slots: List[Dict[str, str]] = []
        by_index: Dict[int, Dict[str, str]] = {}

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
                idx = getattr(tc, "index", None)
                fn = getattr(tc, "function", None)
                name = getattr(fn, "name", None) if fn is not None else None
                if idx is not None:
                    slot = by_index.get(idx)
                    if slot is None:
                        slot = {"id": "", "name": "", "arguments": ""}
                        by_index[idx] = slot
                        slots.append(slot)
                elif name or not slots:
                    slot = {"id": "", "name": "", "arguments": ""}
                    slots.append(slot)
                else:
                    slot = slots[-1]
                if getattr(tc, "id", None):
                    slot["id"] = tc.id
                if fn is not None:
                    if name:
                        slot["name"] = name
                    if getattr(fn, "arguments", None):
                        slot["arguments"] += fn.arguments

        tool_calls = slots
        content = "".join(content_parts) if content_parts else None
        return {"role": "assistant", "content": content, "tool_calls": tool_calls}
