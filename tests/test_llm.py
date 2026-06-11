from types import SimpleNamespace

import pytest

from agentcore.llm import LLMClient


def _delta_chunk(content=None, tool_calls=None):
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta, finish_reason=None)])


def _tc(index, id=None, name=None, arguments=None):
    fn = SimpleNamespace(name=name, arguments=arguments)
    return SimpleNamespace(index=index, id=id, function=fn)


class _FakeCompletions:
    def __init__(self, chunks):
        self._chunks = chunks
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return iter(self._chunks)


class _FakeClient:
    def __init__(self, chunks):
        self.chat = SimpleNamespace(completions=_FakeCompletions(chunks))


def test_streams_content_tokens_and_returns_text():
    chunks = [_delta_chunk(content="Hel"), _delta_chunk(content="lo")]
    client = LLMClient(client=_FakeClient(chunks))
    tokens = []
    msg = client.chat(model="m", messages=[{"role": "user", "content": "hi"}],
                      on_token=tokens.append)
    assert tokens == ["Hel", "lo"]
    assert msg["content"] == "Hello"
    assert msg["tool_calls"] == []


def test_assembles_streamed_tool_call_fragments():
    chunks = [
        _delta_chunk(tool_calls=[_tc(0, id="call_1", name="get_valuation", arguments='{"sto')]),
        _delta_chunk(tool_calls=[_tc(0, arguments='ck_no": "2330"}')]),
    ]
    client = LLMClient(client=_FakeClient(chunks))
    msg = client.chat(model="m", messages=[{"role": "user", "content": "hi"}])
    assert msg["content"] is None
    assert msg["tool_calls"] == [
        {"id": "call_1", "name": "get_valuation", "arguments": '{"stock_no": "2330"}'}
    ]


def test_passes_tools_and_tool_choice_when_tools_given():
    tools = [{"type": "function", "function": {"name": "x"}}]
    client = LLMClient(client=_FakeClient([_delta_chunk(content="x")]))
    client.chat(model="m", messages=[], tools=tools)
    kwargs = client._client.chat.completions.last_kwargs
    assert kwargs["stream"] is True
    assert kwargs["tool_choice"] == "auto"
    assert kwargs["tools"] == tools


class _ModelRoutedCompletions:
    """Raises a status error for models listed in `fail`; streams for the rest."""
    def __init__(self, fail, status=429):
        self._fail = set(fail)
        self._status = status
        self.used = []

    def create(self, **kwargs):
        m = kwargs["model"]
        self.used.append(m)
        if m in self._fail:
            err = RuntimeError("boom"); err.status_code = self._status
            raise err
        return iter([_delta_chunk(content="ok from " + m)])


def _routed(fail, status=429):
    comp = _ModelRoutedCompletions(fail, status)
    client = LLMClient(client=SimpleNamespace(chat=SimpleNamespace(completions=comp)))
    return client, comp


def test_chat_falls_back_to_next_model_on_transient_error():
    client, comp = _routed({"primary"}, status=429)
    msg = client.chat(model="primary", messages=[], fallback_models=["backup"],
                      max_retries=0, backoff=0)
    assert msg["content"] == "ok from backup"
    assert comp.used == ["primary", "backup"]


def test_chat_does_not_fall_back_on_non_transient_error():
    client, comp = _routed({"primary"}, status=400)  # client error, not transient
    with pytest.raises(Exception):
        client.chat(model="primary", messages=[], fallback_models=["backup"],
                    max_retries=0, backoff=0)
    assert comp.used == ["primary"]            # never tried the backup


def test_chat_falls_back_on_model_not_found_404():
    client, comp = _routed({"primary"}, status=404)
    msg = client.chat(model="primary", messages=[], fallback_models=["backup"],
                      max_retries=0, backoff=0)
    assert msg["content"] == "ok from backup"


def test_chat_raises_when_all_models_fail():
    client, comp = _routed({"primary", "backup"}, status=429)
    with pytest.raises(Exception):
        client.chat(model="primary", messages=[], fallback_models=["backup"],
                    max_retries=0, backoff=0)
    assert comp.used == ["primary", "backup"]


def test_raises_when_no_key_and_no_client(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="NVIDIA_API_KEY"):
        LLMClient()


def test_reads_custom_api_key_env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    # Constructs the OpenAI client offline (no network) when the key is present.
    client = LLMClient(base_url="https://openrouter.ai/api/v1",
                       api_key_env="OPENROUTER_API_KEY")
    assert client._client is not None


def test_missing_custom_key_raises_with_that_env_name(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        LLMClient(api_key_env="OPENROUTER_API_KEY")


class _FlakyCompletions:
    def __init__(self, chunks, fail_times, status_code=503):
        self._chunks = chunks
        self._fail_times = fail_times
        self._status = status_code
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        if self.calls <= self._fail_times:
            err = RuntimeError("transient boom")
            err.status_code = self._status
            raise err
        return iter(self._chunks)


class _FlakyClient:
    def __init__(self, chunks, fail_times, status_code=503):
        self.chat = SimpleNamespace(
            completions=_FlakyCompletions(chunks, fail_times, status_code))


def test_retries_transient_5xx_then_succeeds():
    client = LLMClient(client=_FlakyClient([_delta_chunk(content="ok")], fail_times=2))
    msg = client.chat(model="m", messages=[], max_retries=3, backoff=0)
    assert msg["content"] == "ok"
    assert client._client.chat.completions.calls == 3  # 2 failures + 1 success


def test_gives_up_after_max_retries():
    client = LLMClient(client=_FlakyClient([_delta_chunk(content="ok")], fail_times=9))
    with pytest.raises(RuntimeError, match="transient"):
        client.chat(model="m", messages=[], max_retries=2, backoff=0)
    assert client._client.chat.completions.calls == 3  # initial + 2 retries


def test_does_not_retry_non_transient_4xx():
    client = LLMClient(client=_FlakyClient([_delta_chunk(content="x")],
                                           fail_times=1, status_code=400))
    with pytest.raises(RuntimeError):
        client.chat(model="m", messages=[], max_retries=3, backoff=0)
    assert client._client.chat.completions.calls == 1  # 400 is not retried


def test_assembles_multiple_tool_calls_ordered_by_index():
    chunks = [
        _delta_chunk(tool_calls=[_tc(0, id="c0", name="alpha", arguments="{}")]),
        _delta_chunk(tool_calls=[_tc(1, id="c1", name="beta", arguments='{"x":1}')]),
    ]
    client = LLMClient(client=_FakeClient(chunks))
    msg = client.chat(model="m", messages=[])
    assert [tc["name"] for tc in msg["tool_calls"]] == ["alpha", "beta"]
    assert [tc["id"] for tc in msg["tool_calls"]] == ["c0", "c1"]


def test_assembles_indexless_tool_calls_as_separate_calls():
    # Google/Gemini's OpenAI-compatible streaming sets index=None and delivers
    # each tool call complete in one delta. They must NOT collapse into one slot
    # (which would overwrite names and concatenate arguments into invalid JSON).
    chunks = [
        _delta_chunk(tool_calls=[_tc(None, id="g1", name="get_valuation",
                                     arguments='{"stock_no":"AAPL"}')]),
        _delta_chunk(tool_calls=[_tc(None, id="g2", name="get_financials",
                                     arguments='{"stock_no":"AAPL"}')]),
    ]
    client = LLMClient(client=_FakeClient(chunks))
    msg = client.chat(model="m", messages=[])
    assert [tc["name"] for tc in msg["tool_calls"]] == ["get_valuation", "get_financials"]
    assert [tc["arguments"] for tc in msg["tool_calls"]] == [
        '{"stock_no":"AAPL"}', '{"stock_no":"AAPL"}']
    assert [tc["id"] for tc in msg["tool_calls"]] == ["g1", "g2"]


def test_assembles_indexless_fragmented_tool_call():
    # An argument-only continuation (no name, index None) appends to the call in
    # progress rather than starting a new one.
    chunks = [
        _delta_chunk(tool_calls=[_tc(None, id="g1", name="get_valuation",
                                     arguments='{"sto')]),
        _delta_chunk(tool_calls=[_tc(None, arguments='ck_no":"AAPL"}')]),
    ]
    client = LLMClient(client=_FakeClient(chunks))
    msg = client.chat(model="m", messages=[])
    assert msg["tool_calls"] == [
        {"id": "g1", "name": "get_valuation", "arguments": '{"stock_no":"AAPL"}'}]
