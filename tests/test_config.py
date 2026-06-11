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


def test_google_provider_switches_base_url_key_and_models():
    r = resolve({"LLM_PROVIDER": "google"})
    assert r["provider"] == "google"
    assert r["base_url"] == "https://generativelanguage.googleapis.com/v1beta/openai"
    assert r["api_key_env"] == "GOOGLE_API_KEY"
    assert r["reasoner"] == "gemma-4-31b-it"
    assert r["tool_caller"] == "gemma-4-31b-it"


def test_provider_name_is_case_insensitive():
    assert resolve({"LLM_PROVIDER": "OpenRouter"})["provider"] == "openrouter"


def test_per_provider_model_env_overrides_active_provider_default():
    r = resolve({"LLM_PROVIDER": "openrouter",
                 "OPENROUTER_MODEL_REASONER": "z-ai/glm-4.5-air:free",
                 "OPENROUTER_MODEL_TOOL_CALLER": "openai/gpt-oss-120b:free"})
    assert r["reasoner"] == "z-ai/glm-4.5-air:free"
    assert r["tool_caller"] == "openai/gpt-oss-120b:free"


def test_provider_model_overrides_are_isolated_per_provider():
    # OpenRouter overrides must NOT leak into an nvidia run.
    env = {"LLM_PROVIDER": "nvidia",
           "OPENROUTER_MODEL_REASONER": "moonshotai/kimi-k2.6:free",
           "OPENROUTER_MODEL_TOOL_CALLER": "openai/gpt-oss-120b:free",
           "NVIDIA_MODEL_REASONER": "moonshotai/kimi-k2.6"}
    r = resolve(env)
    assert r["reasoner"] == "moonshotai/kimi-k2.6"            # nvidia override
    assert r["tool_caller"] == "meta/llama-3.3-70b-instruct"  # nvidia default, openrouter ignored


def test_model_env_parses_comma_list_into_primary_and_fallbacks():
    r = resolve({"LLM_PROVIDER": "openrouter",
                 "OPENROUTER_MODEL_REASONER":
                     "deepseek/deepseek-v4-flash:free, openai/gpt-oss-120b:free"})
    assert r["reasoner"] == "deepseek/deepseek-v4-flash:free"      # primary
    assert r["reasoner_fallbacks"] == ["openai/gpt-oss-120b:free"]  # the rest, whitespace stripped


def test_single_model_has_no_fallbacks():
    r = resolve({"LLM_PROVIDER": "openrouter"})
    assert r["reasoner_fallbacks"] == [] and r["tool_caller_fallbacks"] == []


def test_unknown_provider_raises():
    with pytest.raises(ValueError, match="LLM_PROVIDER"):
        resolve({"LLM_PROVIDER": "bogus"})


def test_discussion_rounds_default_and_override(monkeypatch):
    import importlib
    import committee.config as cfg
    monkeypatch.delenv("DISCUSSION_ROUNDS", raising=False)
    importlib.reload(cfg)
    assert cfg.DISCUSSION_ROUNDS == 2
    monkeypatch.setenv("DISCUSSION_ROUNDS", "0")
    importlib.reload(cfg)
    assert cfg.DISCUSSION_ROUNDS == 0
    # monkeypatch auto-undoes the env var but does not re-reload the module, so
    # restore committee.config to its default-env state for later tests.
    monkeypatch.delenv("DISCUSSION_ROUNDS", raising=False)
    importlib.reload(cfg)
