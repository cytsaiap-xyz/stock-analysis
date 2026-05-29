import os
from typing import Any, Dict, Mapping

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Per-provider connection + two-tier model defaults. Both providers are
# OpenAI-compatible, so switching is just base_url + api key + model ids.
# Pick the provider with LLM_PROVIDER; override any model with MODEL_* env.
_PROVIDERS: Dict[str, Dict[str, str]] = {
    "nvidia": {
        "base_url": NVIDIA_BASE_URL,
        "api_key_env": "NVIDIA_API_KEY",
        "reasoner": "moonshotai/kimi-k2.6",
        "tool_caller": "meta/llama-3.3-70b-instruct",
    },
    "openrouter": {
        "base_url": OPENROUTER_BASE_URL,
        "api_key_env": "OPENROUTER_API_KEY",
        "reasoner": "deepseek/deepseek-v4-flash:free",
        "tool_caller": "qwen/qwen3-coder:free",
    },
}


def resolve(env: Mapping[str, str]) -> Dict[str, Any]:
    """Resolve provider connection + model tiers from an environment mapping.

    Pure (takes the env in) so it is testable without mutating os.environ.
    MODEL_REASONER / MODEL_TOOL_CALLER override the provider's defaults.
    """
    provider = env.get("LLM_PROVIDER", "nvidia").lower()
    if provider not in _PROVIDERS:
        raise ValueError("Unknown LLM_PROVIDER: {!r} (expected one of {})".format(
            provider, ", ".join(sorted(_PROVIDERS))))
    p = _PROVIDERS[provider]
    return {
        "provider": provider,
        "base_url": p["base_url"],
        "api_key_env": p["api_key_env"],
        "reasoner": env.get("MODEL_REASONER", p["reasoner"]),
        "tool_caller": env.get("MODEL_TOOL_CALLER", p["tool_caller"]),
    }


_R = resolve(os.environ)
LLM_PROVIDER = _R["provider"]
BASE_URL = _R["base_url"]
API_KEY_ENV = _R["api_key_env"]
MODEL_REASONER = _R["reasoner"]
MODEL_TOOL_CALLER = _R["tool_caller"]

CACHE_DIR = os.environ.get("CACHE_DIR", "cache")

# Chair self-reflection passes before VERIFY (0 disables). Default on, env-overridable.
REFLECTION_PASSES = int(os.environ.get("REFLECTION_PASSES", "1"))
