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


def test_raises_when_no_key_and_no_client(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="NVIDIA_API_KEY"):
        LLMClient()


def test_assembles_multiple_tool_calls_ordered_by_index():
    chunks = [
        _delta_chunk(tool_calls=[_tc(0, id="c0", name="alpha", arguments="{}")]),
        _delta_chunk(tool_calls=[_tc(1, id="c1", name="beta", arguments='{"x":1}')]),
    ]
    client = LLMClient(client=_FakeClient(chunks))
    msg = client.chat(model="m", messages=[])
    assert [tc["name"] for tc in msg["tool_calls"]] == ["alpha", "beta"]
    assert [tc["id"] for tc in msg["tool_calls"]] == ["c0", "c1"]
