import pytest
from agentcore.tools import Tool, ToolRegistry


def _sample_tool():
    return Tool(
        name="get_valuation",
        description="Get P/E etc.",
        parameters={
            "type": "object",
            "properties": {"stock_no": {"type": "string"}},
            "required": ["stock_no"],
        },
        fn=lambda stock_no: {"pe": 22.5},
    )


def test_to_openai_schema_shape():
    schema = _sample_tool().to_openai_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "get_valuation"
    assert schema["function"]["parameters"]["required"] == ["stock_no"]


def test_registry_register_get_and_schemas():
    reg = ToolRegistry()
    reg.register(_sample_tool())
    assert reg.get("get_valuation").fn(stock_no="2330") == {"pe": 22.5}
    schemas = reg.schemas(["get_valuation"])
    assert len(schemas) == 1 and schemas[0]["function"]["name"] == "get_valuation"


def test_get_unknown_tool_raises():
    with pytest.raises(KeyError):
        ToolRegistry().get("nope")
