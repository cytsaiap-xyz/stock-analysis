import pytest

from committee.config import resolve


def test_default_provider_is_nvidia():
    r = resolve({})
    assert r["provider"] == "nvidia"
    assert r["base_url"] == "https://integrate.api.nvidia.com/v1"
    assert r["api_key_env"] == "NVIDIA_API_KEY"
    assert r["reasoner"] == "moonshotai/kimi-k2.6"
    assert r["tool_caller"] == "meta/llama-3.3-70b-instruct"


def test_openrouter_provider_switches_base_url_key_and_models():
    r = resolve({"LLM_PROVIDER": "openrouter"})
    assert r["provider"] == "openrouter"
    assert r["base_url"] == "https://openrouter.ai/api/v1"
    assert r["api_key_env"] == "OPENROUTER_API_KEY"
    assert r["reasoner"] == "deepseek/deepseek-v4-flash:free"
    assert r["tool_caller"] == "qwen/qwen3-coder:free"


def test_provider_name_is_case_insensitive():
    assert resolve({"LLM_PROVIDER": "OpenRouter"})["provider"] == "openrouter"


def test_explicit_model_env_overrides_provider_default():
    r = resolve({"LLM_PROVIDER": "openrouter",
                 "MODEL_REASONER": "z-ai/glm-4.5-air:free"})
    assert r["reasoner"] == "z-ai/glm-4.5-air:free"
    assert r["tool_caller"] == "qwen/qwen3-coder:free"  # untouched default


def test_unknown_provider_raises():
    with pytest.raises(ValueError, match="LLM_PROVIDER"):
        resolve({"LLM_PROVIDER": "bogus"})
